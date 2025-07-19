import pytest

from src.diff_engine import DiffEngine


@pytest.fixture
def old_objects():
    return [
        {"id": "1:1", "text": "Idea A", "position": {"x": 100}, "color": {"r": 1}},
        {"id": "1:2", "text": "Idea B", "position": {"x": 200}, "color": {"r": 0}},
        {"id": "1:3", "text": "Idea C", "position": {"x": 300}, "color": {"r": 0}},
    ]


@pytest.fixture
def new_objects():
    return [
        # Modified text
        {"id": "1:1", "text": "Idea A updated", "position": {"x": 100}, "color": {"r": 1}},
        # Unchanged
        {"id": "1:2", "text": "Idea B", "position": {"x": 200}, "color": {"r": 0}},
        # Added
        {"id": "1:4", "text": "New Idea D", "position": {"x": 400}, "color": {"r": 0}},
    ]


def test_diff_detection(old_objects, new_objects):
    """オブジェクトの追加、変更、削除を正しく検出できるかテストする"""
    diff = DiffEngine.detect_changes(old_objects, new_objects)

    assert len(diff["added"]) == 1
    assert diff["added"][0]["id"] == "1:4"

    assert len(diff["deleted"]) == 1
    assert diff["deleted"][0]["id"] == "1:3"

    assert len(diff["modified"]) == 1
    assert diff["modified"][0]["id"] == "1:1"
    assert diff["modified"][0]["new_text"] == "Idea A updated"
