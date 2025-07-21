import os
import pytest
from unittest.mock import patch, mock_open

from src.file_io import FileIO

@pytest.fixture
def create_dummy_logs(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "log_2023-01-01.md").write_text("Log 1")
    (log_dir / "log_2023-01-02.md").write_text("Log 2")
    (log_dir / "other_file.txt").write_text("Not a log")
    return str(log_dir)

def test_read_all_logs_aggregates_all_log_files(create_dummy_logs):
    """全てのログファイルの内容が結合されて返されることをテストする"""
    log_dir = create_dummy_logs
    all_logs = FileIO.read_all_logs(log_dir)
    assert "Log 1" in all_logs
    assert "Log 2" in all_logs
    assert "Not a log" not in all_logs

def test_read_all_logs_no_directory():
    """ログディレクトリが存在しない場合に空文字列が返されることをテストする"""
    all_logs = FileIO.read_all_logs("non_existent_dir")
    assert all_logs == ""
