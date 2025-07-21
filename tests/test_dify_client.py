import os
from unittest.mock import patch, MagicMock
import pytest

from src.dify_client import DifyClient  # Assuming DifyClient is in src/dify_client.py


@pytest.fixture
def mock_dify_success_response():
    return {"data": {"outputs": {"text": "Mocked Dify response text."}}}


@pytest.fixture
def mock_dify_error_response():
    return "Dify API Error: Invalid Request"


def test_invoke_success(mock_dify_success_response, capsys):
    """Dify APIが正常に実行され、ログが出力されることをテストする"""
    with patch("requests.post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = mock_dify_success_response
        mock_post.return_value = mock_res

        os.environ["DIFY_API_KEY"] = "test_dify_key"
        os.environ["DIFY_API_URL"] = "https://api.dify.ai/v1/workflows/run"
        os.environ["DIFY_WORKFLOW_ID"] = "test_workflow_id"

        os.environ["FIGMA_CLI_DEBUG_LOGGING"] = "true" # Enable debug logging for this test
        client = DifyClient()
        outline_content = "Test outline content"
        all_logs_content = "Test logs content"

        result = client.invoke(outline_content, all_logs_content)

        # Check if requests.post was called with correct arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["inputs"]["outline_content"] == outline_content
        assert kwargs["json"]["inputs"]["all_logs_content"] == all_logs_content
        assert kwargs["json"]["workflow_id"] == "test_workflow_id"
        assert "Authorization" in kwargs["headers"]
        assert kwargs["headers"]["Authorization"] == "Bearer test_dify_key"

        # Check the returned result
        assert result == mock_dify_success_response["data"]["outputs"]["text"]

        # Check print statements using capsys
        captured = capsys.readouterr()
        assert "--- Dify API Request ---" in captured.out
        assert "URL: https://api.dify.ai/v1/workflows/run" in captured.out
        assert (
            "Headers: {'Authorization': 'Bearer test_dify_key', 'Content-Type': 'application/json'}"
            in captured.out
        )
        assert (
            f"Data: {{'inputs': {{'outline_content': '{outline_content}', 'all_logs_content': '{all_logs_content}'}}, 'response_mode': 'blocking', 'user': 'figma-cli-user-01', 'workflow_id': 'test_workflow_id'}}"
            in captured.out
        )
        assert (
            "--- Dify API Error Response ---" not in captured.out
        )  # Ensure error log is not present


@pytest.mark.parametrize("debug_logging_enabled", [True, False])
@patch("requests.post")
def test_invoke_debug_logging_control(mock_post, capsys, debug_logging_enabled):
    """Dify APIのリクエスト/レスポンスログがFIGMA_CLI_DEBUG_LOGGING環境変数で制御されることをテストする"""
    # Setup environment variable
    if debug_logging_enabled:
        os.environ["FIGMA_CLI_DEBUG_LOGGING"] = "true"
    else:
        if "FIGMA_CLI_DEBUG_LOGGING" in os.environ:
            del os.environ["FIGMA_CLI_DEBUG_LOGGING"]

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"data": {"outputs": {"text": "Mocked Dify response text."}}}
    mock_post.return_value = mock_res

    os.environ["DIFY_API_KEY"] = "test_dify_key"
    os.environ["DIFY_API_URL"] = "https://api.dify.ai/v1" # Use base URL as it's now handled in invoke
    os.environ["DIFY_WORKFLOW_ID"] = "test_workflow_id"

    client = DifyClient()
    client.invoke("Test outline content", "Test logs content")

    captured = capsys.readouterr()

    if debug_logging_enabled:
        assert "--- Dify API Request ---" in captured.out
        assert "--- Dify API Error Response ---" not in captured.out # No error in success case
    else:
        assert "--- Dify API Request ---" not in captured.out
        assert "--- Dify API Error Response ---" not in captured.out

    # Test error logging control
    mock_res.status_code = 400
    mock_res.text = "Dify API Error: Invalid Request"
    mock_res.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request")

    with pytest.raises(requests.exceptions.HTTPError):
        client.invoke("Test outline content", "Test logs content")

    captured = capsys.readouterr() # Capture output after error

    if debug_logging_enabled:
        assert "--- Dify API Error Response ---" in captured.out
        assert "Status Code: 400" in captured.out
        assert "Response Body: Dify API Error: Invalid Request" in captured.out
    else:
        assert "--- Dify API Error Response ---" not in captured.out

    # Clean up environment variable
    if "FIGMA_CLI_DEBUG_LOGGING" in os.environ:
        del os.environ["FIGMA_CLI_DEBUG_LOGGING"]


def test_invoke_api_error(mock_dify_error_response, capsys):
    """Dify APIがエラーを返した場合に例外を送出し、エラーログが出力されることをテストする"""
    # This test is modified to respect the debug_logging_enabled flag for its assertions
    # For this test, we assume debug logging is enabled to check error output
    os.environ["FIGMA_CLI_DEBUG_LOGGING"] = "true" # Force enable for this specific test

    with patch("requests.post") as mock_post:
        mock_res = MagicMock()
        mock_res.status_code = 400
        mock_res.text = mock_dify_error_response
        mock_res.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Bad Request"
        )
        mock_post.return_value = mock_res

        os.environ["DIFY_API_KEY"] = "test_dify_key"
        os.environ["DIFY_API_URL"] = "https://api.dify.ai/v1" # Use base URL
        os.environ["DIFY_WORKFLOW_ID"] = "test_workflow_id"

        client = DifyClient()
        outline_content = "Test outline content"
        all_logs_content = "Test logs content"

        with pytest.raises(requests.exceptions.HTTPError):
            client.invoke(outline_content, all_logs_content)

        # Check print statements using capsys
        captured = capsys.readouterr()
        assert "--- Dify API Request ---" in captured.out
        assert "--- Dify API Error Response ---" in captured.out
        assert "Status Code: 400" in captured.out
        assert f"Response Body: {mock_dify_error_response}" in captured.out

    # Clean up environment variable
    if "FIGMA_CLI_DEBUG_LOGGING" in os.environ:
        del os.environ["FIGMA_CLI_DEBUG_LOGGING"]


# Assuming DifyClient needs requests, add import for requests.exceptions.HTTPError
import requests
