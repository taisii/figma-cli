import os
import pytest
from unittest.mock import patch, MagicMock, mock_open, call

from src.main_controller import MainController


@pytest.fixture
def mock_dependencies():
    with patch('src.main_controller.FigmaClient') as MockFigmaClient, \
         patch('src.main_controller.StructureParser') as MockStructureParser, \
         patch('src.main_controller.PromptGenerator') as MockPromptGenerator, \
         patch('src.main_controller.CacheManager') as MockCacheManager, \
         patch('src.main_controller.os') as mock_os, \
         patch('src.main_controller.os.path') as mock_os_path, \
         patch('builtins.open', new_callable=mock_open) as mock_file, \
         patch('src.main_controller.yaml.safe_load') as mock_yaml_load, \
         patch('src.main_controller.dotenv.load_dotenv'), \
         patch('src.main_controller.generativeai') as mock_genai, \
         patch('src.main_controller.DifyClient') as MockDifyClient, \
         patch('src.main_controller.requests.post') as mock_requests_post:

        # Setup mocks
        mock_figma_client = MockFigmaClient.return_value
        mock_figma_client.get_figma_objects.return_value = [{'id': '1', 'text': 'new data'}]

        mock_parser = MockStructureParser.return_value
        mock_parser.parse.return_value = {'clusters': [], 'connections': [], 'objects': []}

        MockPromptGenerator.generate_initial_prompt.return_value = "Initial Outline"
        MockPromptGenerator.generate_update_prompt.return_value = "Update Outline"
        MockPromptGenerator.generate_log_prompt.return_value = "Old Log Content"
        MockPromptGenerator.generate_daily_report_prompt.return_value = "New Daily Report Content"


        mock_genai.GenerativeModel.return_value.generate_content.side_effect = [
            MagicMock(text="Generated Outline"),
            MagicMock(text="New Daily Report Content")
        ]

        mock_yaml_load.return_value = {'color_tags': {}, 'clustering_threshold': 100, 'gemini_model_name': 'gemini-pro'}

        mock_dify_client = MockDifyClient.return_value
        # DifyClientのモックがテキストを返すように設定
        mock_dify_client.invoke.return_value = "Generated Strategy"


        yield {
            'figma_client': mock_figma_client,
            'parser': mock_parser,
            'prompt_generator': MockPromptGenerator,
            'cache_manager': MockCacheManager,
            'mock_os': mock_os,
            'mock_file': mock_file,
            'mock_genai': mock_genai,
            'dify_client': mock_dify_client,
            'mock_os_path': mock_os_path,
            'mock_requests_post': mock_requests_post
        }


def test_initial_run(mock_dependencies):
    """初回実行時のフローをテストする"""
    mock_dependencies['cache_manager'].load_cache.return_value = None # No cache
    mock_dependencies['mock_os'].path.exists.side_effect = [False, False] # outline.md, outline_history/
    mock_dependencies['mock_os'].rename.assert_not_called()

    controller = MainController()
    controller.run()

    # Verification
    mock_dependencies['figma_client'].get_figma_objects.assert_called_once()
    mock_dependencies['parser'].parse.assert_called_once()
    mock_dependencies['prompt_generator'].generate_initial_prompt.assert_called_once()
    mock_dependencies['prompt_generator'].generate_daily_report_prompt.assert_called_once()
    mock_dependencies['cache_manager'].save_cache.assert_called_once_with([{'id': '1', 'text': 'new data'}], 'cache.json')
    # Check if outline and log are written
    assert mock_dependencies['mock_file']().write.call_count == 2
    mock_dependencies['mock_file']().write.assert_any_call('Generated Outline')
    mock_dependencies['mock_file']().write.assert_any_call('New Daily Report Content')


def test_update_run_uses_daily_report_prompt(mock_dependencies):
    """差分更新時に新しい日報プロンプト(generate_daily_report_prompt)が使われることをテストする"""
    # Simulate existing cache and outline
    mock_dependencies['cache_manager'].load_cache.return_value = [{'id': '0', 'text': 'old data'}]
    mock_dependencies['mock_os'].path.exists.side_effect = [True, True, True] # outline.md, outline_history/, logs/

    with patch('src.main_controller.DiffEngine.detect_changes') as mock_diff:
        mock_diff.return_value = {'added': [{'id': 'new', 'text': 'new data'}], 'modified': [], 'deleted': []}

        controller = MainController()
        controller.run()

        # Verification
        mock_dependencies['prompt_generator'].generate_update_prompt.assert_called_once()
        mock_dependencies['prompt_generator'].generate_daily_report_prompt.assert_called_once() # 新しいプロンプトが呼ばれる
        mock_dependencies['prompt_generator'].generate_log_prompt.assert_not_called() # 古いプロンプトは呼ばれない
        # Check if the correct log content is written
        mock_dependencies['mock_file']().write.assert_any_call('New Daily Report Content')


def test_update_run(mock_dependencies):
    """差分更新時のフローをテストする"""
    # Simulate existing cache and outline
    mock_dependencies['cache_manager'].load_cache.return_value = [{'id': '0', 'text': 'old data'}]
    mock_dependencies['mock_os'].path.exists.side_effect = [True, True, True] # outline.md, outline_history/, logs/

    with patch('src.main_controller.DiffEngine.detect_changes') as mock_diff:
        mock_diff.return_value = {'added': [{'id': 'new', 'text': 'new data'}], 'modified': [], 'deleted': []}

        controller = MainController()
        controller.run()

        # Verification
        mock_dependencies['figma_client'].get_figma_objects.assert_called_once()
        mock_diff.assert_called_once()
        mock_dependencies['prompt_generator'].generate_update_prompt.assert_called_once()
        mock_dependencies['prompt_generator'].generate_daily_report_prompt.assert_called_once()
        mock_dependencies['cache_manager'].save_cache.assert_called_once()
        # Check if history, outline, and log are written
        assert mock_dependencies['mock_file']().write.call_count == 2
        mock_dependencies['mock_os'].rename.assert_called_once() # outline.md should be renamed
        mock_dependencies['mock_file']().write.assert_any_call('Generated Outline')
        mock_dependencies['mock_file']().write.assert_any_call('New Daily Report Content')


@patch('sys.stdout', new_callable=MagicMock)
def test_run_with_no_changes(mock_stdout, mock_dependencies):
    """差分がない場合にAI生成がスキップされることをテストする"""
    # Simulate existing cache and outline, and no changes
    mock_dependencies['cache_manager'].load_cache.return_value = [{'id': '0', 'text': 'old data'}]
    mock_dependencies['figma_client'].get_figma_objects.return_value = [{'id': '0', 'text': 'old data'}] # No changes
    with patch('src.main_controller.DiffEngine.detect_changes') as mock_diff:
        mock_diff.return_value = {'added': [], 'modified': [], 'deleted': []}
        controller = MainController()
        controller.run()

        # Verification
        mock_dependencies['figma_client'].get_figma_objects.assert_called_once()
        mock_dependencies['cache_manager'].save_cache.assert_called_once() # Cache should still be updated
        mock_dependencies['mock_genai'].GenerativeModel.return_value.generate_content.assert_not_called() # AI should not be called
        mock_dependencies['mock_file']().write.assert_not_called() # No files should be written
        mock_stdout.write.assert_any_call("No changes detected. Skipping AI generation.") # Check for specific message
        # Verify all progress messages are called
        expected_calls = [
            call("Step 1/6: Loading context and preparing files..."),
            call("\n"), # print adds a newline
            call("Step 2/6: Fetching data from Figma API..."),
            call("\n"), # print adds a newline
            call("No changes detected. Skipping AI generation."),
            call("\n"), # print adds a newline
        ]
        mock_stdout.write.assert_has_calls(expected_calls, any_order=True)

def test_daily_report_uses_direct_gemini_api(mock_dependencies):
    """日報生成がGemini APIを直接利用し、Dify APIを利用しないことをテストする"""
    mock_dependencies['cache_manager'].load_cache.return_value = None # No cache
    mock_dependencies['mock_os'].path.exists.side_effect = [False, False] # outline.md, outline_history/

    controller = MainController()
    controller.run()

    # Verification
    # 日報生成のためにGemini APIが呼ばれることを確認
    gen_ai_calls = mock_dependencies['mock_genai'].GenerativeModel.return_value.generate_content.call_args_list
    assert len(gen_ai_calls) == 2
    # 2番目の呼び出しが日報生成
    log_prompt_call = gen_ai_calls[1]
    # Dify Clientが呼ばれないことを確認
    mock_dependencies['dify_client'].invoke.assert_not_called()

def test_strategy_flag_triggers_strategy_cycle(mock_dependencies):
    """--strategy フラグが指定された場合に strategy_cycle が呼ばれることをテストする"""
    # We need to patch MainController for this test to isolate the call
    with patch('src.main_controller.MainController') as MockMainController_local:
        instance = MockMainController_local.return_value
        with patch('sys.argv', ['run.py', '--strategy']):
            from run import main
            main()
            instance.execute_strategy_cycle.assert_called_once()


@patch.dict(os.environ, {"DIFY_API_KEY": "test_api_key", "DIFY_WORKFLOW_ID": "test_workflow_id"})
@patch('requests.post')
def test_dify_client_invoke(mock_post):
    """DifyClientが正しくAPIを呼び出し、結果を返すかテストする"""
    from src.main_controller import DifyClient

    # Mock the successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'data': {
            'outputs': {
                'text': 'Generated Strategy Text'
            }
        }
    }
    mock_post.return_value = mock_response

    client = DifyClient()
    result = client.invoke("Test Outline Content", "Test Logs Content")

    # Verify the request
    expected_url = "https://api.dify.ai/v1/workflows/run"
    expected_headers = {
        'Authorization': 'Bearer test_api_key',
        'Content-Type': 'application/json'
    }
    expected_data = {
        'inputs': {
            'outline_content': "Test Outline Content",
            'all_logs_content': "Test Logs Content"
        },
        'response_mode': 'blocking',
        'user': 'figma-cli-user-01',
        'workflow_id': 'test_workflow_id'
    }
    mock_post.assert_called_once_with(expected_url, headers=expected_headers, json=expected_data)

    # Verify the result
    assert result == "Generated Strategy Text"


@patch.dict(os.environ, {"DIFY_API_KEY": "test_api_key", "DIFY_WORKFLOW_ID": "test_workflow_id"})
@patch('requests.post')
def test_dify_client_invoke_api_error(mock_post):
    """DifyClientがAPIエラーを適切に処理するかテストする"""
    from src.main_controller import DifyClient

    # Mock the error API response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = Exception("API Error")
    mock_post.return_value = mock_response

    with pytest.raises(Exception, match="API Error"):
        client = DifyClient()
        client.invoke("Test Outline", "Test Logs")

def test_execute_strategy_cycle_orchestrates_correctly(mock_dependencies):
    """execute_strategy_cycleが正しく各モジュールを呼び出すかテストする"""
    # Use mocks from fixture
    mock_file = mock_dependencies['mock_file']
    mock_dify_client = mock_dependencies['dify_client']
    mock_os = mock_dependencies['mock_os']
    mock_os_path = mock_dependencies['mock_os_path']

    # Create a specific mock for the handle of the file to be written
    mock_write_handle = mock_open().return_value

    # Mock open for reading config.yaml, outline.md and writing strategy file
    mock_file.side_effect = [
        mock_open(read_data="""color_tags: {}
clustering_threshold: 100
gemini_model_name: gemini-pro""").return_value, # 1. config.yaml in MainController.__init__
        mock_open(read_data="Test Outline").return_value, # 2. outline.md in execute_strategy_cycle
        mock_write_handle, # 3. For writing strategy_YYYYMMDD.md
    ]

    # We also need to mock dotenv separately to avoid file read order issues
    with patch('src.main_controller.dotenv.load_dotenv') as mock_load_dotenv, \
         patch('src.main_controller.FileIO.read_all_logs') as MockFileIOReadAllLogs:
        MockFileIOReadAllLogs.return_value = "Test Logs"

        # DifyClient's mock is configured to return a simple string
        mock_dify_client.invoke.return_value = "Generated Strategy"
        mock_os_path.exists.return_value = False

        controller = MainController()
        controller.execute_strategy_cycle()

        mock_file.assert_any_call("outline.md", "r")
        MockFileIOReadAllLogs.assert_called_once()
        # Verify that the prompt generator is no longer called
        mock_dependencies['prompt_generator'].generate_strategy_prompt.assert_not_called()
        # Verify DifyClient's invoke was called with the correct arguments
        mock_dify_client.invoke.assert_called_once_with("Test Outline", "Test Logs")
        mock_os.makedirs.assert_called_once_with("output/proposals")
        # Assert that write was called on the specific mock handle
        mock_write_handle.write.assert_called_once_with("Generated Strategy")
