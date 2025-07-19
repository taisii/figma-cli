import json
import os
from unittest.mock import patch, MagicMock

import pytest

from src.figma_client import FigmaClient


@pytest.fixture
def mock_response():
    with open("tests/dummy_response.json") as f:
        return json.load(f)


def test_get_figma_objects_success(mock_response):
    """Figma APIから正常にオブジェクトを取得できることをテストする"""
    with patch("requests.get") as mock_get:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = mock_response
        mock_get.return_value = mock_res

        os.environ["FIGMA_API_TOKEN"] = "test_token"
        os.environ["FIGJAM_BOARD_URL"] = "https://www.figma.com/file/test_board/test"

        client = FigmaClient()
        objects = client.get_figma_objects()

        assert len(objects) == 3
        assert objects[0]["id"] == "1:2"
        assert objects[0]["text"] == "This is a sticky note."


def test_get_figma_objects_api_error():
    """Figma APIがエラーを返した場合に例外を送出するかテストする"""
    with patch("requests.get") as mock_get:
        mock_res = MagicMock()
        mock_res.status_code = 404
        mock_get.return_value = mock_res

        os.environ["FIGMA_API_TOKEN"] = "test_token"
        os.environ["FIGJAM_BOARD_URL"] = "https://www.figma.com/file/test_board/test"

        client = FigmaClient()
        with pytest.raises(Exception):
            client.get_figma_objects()


def test_missing_env_vars():
    """環境変数が不足している場合に例外を送出するかテストする"""
    if "FIGMA_API_TOKEN" in os.environ:
        del os.environ["FIGMA_API_TOKEN"]
    with pytest.raises(ValueError):
        FigmaClient()
