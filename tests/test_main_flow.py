import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

from src.main_controller import MainController


@pytest.fixture
def mock_dependencies():
    with patch('src.main_controller.FigmaClient') as MockFigmaClient,          patch('src.main_controller.StructureParser') as MockStructureParser,          patch('src.main_controller.PromptGenerator') as MockPromptGenerator,          patch('src.main_controller.CacheManager') as MockCacheManager,          patch('src.main_controller.os') as mock_os,          patch('builtins.open', new_callable=mock_open) as mock_file,          patch('src.main_controller.yaml.safe_load') as mock_yaml_load,          patch('src.main_controller.dotenv.load_dotenv'),          patch('src.main_controller.generativeai') as mock_genai:

        # Setup mocks
        mock_figma_client = MockFigmaClient.return_value
        mock_figma_client.get_figma_objects.return_value = [{'id': '1', 'text': 'new data'}]

        mock_parser = MockStructureParser.return_value
        mock_parser.parse.return_value = {'clusters': [], 'connections': [], 'objects': []}

        MockPromptGenerator.generate_initial_prompt.return_value = "Initial Outline"
        MockPromptGenerator.generate_update_prompt.return_value = "Update Outline"
        MockPromptGenerator.generate_log_prompt.return_value = "Generated Log Content"

        mock_genai.GenerativeModel.return_value.generate_content.side_effect = [
            MagicMock(text="Generated Outline"),
            MagicMock(text="Generated Log Content")
        ]

        mock_yaml_load.return_value = {'color_tags': {}, 'clustering_threshold': 100, 'gemini_model_name': 'gemini-pro'}

        yield {
            'figma_client': mock_figma_client,
            'parser': mock_parser,
            'prompt_generator': MockPromptGenerator,
            'cache_manager': MockCacheManager,
            'mock_os': mock_os,
            'mock_file': mock_file,
            'mock_genai': mock_genai
        }


def test_initial_run(mock_dependencies):
    """初回実行時のフローをテストする"""
    mock_dependencies['cache_manager'].load_cache.return_value = None # No cache
    mock_dependencies['mock_os'].path.exists.return_value = False # No old outline

    controller = MainController()
    controller.run()

    # Verification
    mock_dependencies['figma_client'].get_figma_objects.assert_called_once()
    mock_dependencies['parser'].parse.assert_called_once()
    mock_dependencies['prompt_generator'].generate_initial_prompt.assert_called_once()
    mock_dependencies['prompt_generator'].generate_log_prompt.assert_called_once()
    mock_dependencies['cache_manager'].save_cache.assert_called_once_with([{'id': '1', 'text': 'new data'}], 'cache.json')
    # Check if outline and log are written
    assert mock_dependencies['mock_file']().write.call_count == 2
    mock_dependencies['mock_file']().write.assert_any_call('Generated Outline')
    mock_dependencies['mock_file']().write.assert_any_call('Generated Log Content')


def test_update_run(mock_dependencies):
    """差分更新時のフローをテストする"""
    # Simulate existing cache and outline
    mock_dependencies['cache_manager'].load_cache.return_value = [{'id': '0', 'text': 'old data'}]
    mock_dependencies['mock_os'].path.exists.side_effect = [True, True, True] # outline.md, outline_history/, logs/

    with patch('src.main_controller.DiffEngine.detect_changes') as mock_diff:
        mock_diff.return_value = {'added': [], 'modified': [], 'deleted': []}

        controller = MainController()
        controller.run()

        # Verification
        mock_dependencies['figma_client'].get_figma_objects.assert_called_once()
        mock_diff.assert_called_once()
        mock_dependencies['prompt_generator'].generate_update_prompt.assert_called_once()
        mock_dependencies['prompt_generator'].generate_log_prompt.assert_called_once()
        mock_dependencies['cache_manager'].save_cache.assert_called_once()
        # Check if history, outline, and log are written
        assert mock_dependencies['mock_file']().write.call_count == 2
        mock_dependencies['mock_os'].rename.assert_called_once()
        mock_dependencies['mock_file']().write.assert_any_call('Generated Outline')
        mock_dependencies['mock_file']().write.assert_any_call('Generated Log Content')
