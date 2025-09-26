import os
import pytest
from src.reference_manager import ReferenceManager


@pytest.fixture
def setup_references_dir(tmp_path):
    references_dir = tmp_path / "references"
    references_dir.mkdir()
    (references_dir / "paper1.txt").write_text("This is the first paper.")
    (references_dir / "paper2.md").write_text("# Second Paper\nContent of second paper.")
    # PDF and other files can be mocked or small dummy files can be created
    return str(references_dir)

def test_read_references(setup_references_dir):
    """/referencesディレクトリからテキストファイルを正しく読み込めるかテストする"""
    references_data = ReferenceManager.read_references(setup_references_dir)
    
    assert len(references_data) > 0
    assert any("paper1.txt" in item["path"] for item in references_data)
    assert any("This is the first paper." in item["content"] for item in references_data)
    assert any("# Second Paper" in item["content"] for item in references_data)

def test_read_empty_references_dir(tmp_path):
    """空の/referencesディレクトリを読み込んだ場合に空のリストが返ることをテストする"""
    empty_dir = tmp_path / "empty_ref"
    empty_dir.mkdir()
    references_data = ReferenceManager.read_references(str(empty_dir))
    assert references_data == []
