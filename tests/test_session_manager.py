import os
from pathlib import Path

import pytest


def test_initializes_conversation_log(monkeypatch, tmp_path):
    from src import session_manager

    timestamps = iter([
        "2025-10-02T09:00:00Z",
    ])

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: next(timestamps))

    manager = session_manager.SessionManager(tmp_path)

    log_path = manager.conversation_log_path
    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8") == "2025-10-02T09:00:00Z session initialized\n"


def test_load_and_reset_context(monkeypatch, tmp_path):
    from src import session_manager

    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "paper.md").write_text("content", encoding="utf-8")
    (kb_dir / "paper_summary.md").write_text("summary", encoding="utf-8")

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: "2025-10-02T09:00:00Z")

    manager = session_manager.SessionManager(kb_dir)

    manager.load_document("paper.md")
    assert manager.active_documents == [kb_dir / "paper.md"]

    manager.reset_context()
    assert manager.active_documents == []


def test_generate_session_summary(monkeypatch, tmp_path):
    from src import session_manager

    timestamps = iter([
        "2025-10-02T09:00:00Z",
        "2025-10-02T10:00:00Z",
    ])

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: next(timestamps))

    manager = session_manager.SessionManager(tmp_path)
    manager.record_user_message("Discuss the experiment")

    prompts = []

    class DummyResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class DummyModel:
        def generate_content(self, parts):
            prompts.append(parts)
            return DummyResponse("Concise summary")

    manager.model = DummyModel()

    block = manager.generate_session_summary()

    assert "Concise summary" in block
    assert prompts[0][-1] == "Discuss the experiment"
    log_content = manager.conversation_log_path.read_text(encoding="utf-8")
    assert log_content.endswith("Concise summary\n\n")
    assert manager.messages == []


def test_list_documents_warns_missing_summary(monkeypatch, tmp_path):
    from src import session_manager

    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    summary = kb_dir / "alpha_summary.md"
    summary.write_text("summary", encoding="utf-8")
    os.utime(summary, (1000, 1000))

    paper = kb_dir / "beta.md"
    paper.write_text("body", encoding="utf-8")
    os.utime(paper, (2000, 2000))

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: "2025-10-02T09:00:00Z")

    manager = session_manager.SessionManager(kb_dir)
    entries = manager.list_documents()

    assert entries[0].name.startswith("beta.md")
    assert entries[0].missing_summary is True
    assert entries[1].name == "alpha_summary.md"

