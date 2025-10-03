import os


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
    summary_file = kb_dir / "alpha.md"
    summary_file.write_text("summary", encoding="utf-8")

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: "2025-10-02T09:00:00Z")

    manager = session_manager.SessionManager(kb_dir)

    manager.load_document("alpha.md")
    assert manager.active_documents == [kb_dir / "alpha.md"]

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


def test_list_documents_sorted_by_mtime(monkeypatch, tmp_path):
    from src import session_manager

    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    older = kb_dir / "alpha.md"
    older.write_text("summary", encoding="utf-8")
    os.utime(older, (1000, 1000))

    newer = kb_dir / "beta.md"
    newer.write_text("summary", encoding="utf-8")
    os.utime(newer, (2000, 2000))

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: "2025-10-02T09:00:00Z")

    manager = session_manager.SessionManager(kb_dir)
    entries = manager.list_documents()

    assert [entry.name for entry in entries] == ["beta.md", "alpha.md"]
    assert all(entry.missing_summary is False for entry in entries)


def test_auto_preload_respects_limit(monkeypatch, tmp_path):
    from src import session_manager

    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    first = kb_dir / "first.md"
    second = kb_dir / "second.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    os.utime(first, (1000, 1000))
    os.utime(second, (2000, 2000))

    monkeypatch.setattr(session_manager, "current_timestamp", lambda: "2025-10-02T09:00:00Z")

    manager = session_manager.SessionManager(kb_dir, auto_preload=True, preload_limit=1)

    assert manager.active_documents == [second]
