import subprocess
from types import SimpleNamespace


def test_summarize_file_invokes_command(monkeypatch, tmp_path):
    from src import summarize

    markdown = tmp_path / "paper.md"
    markdown.write_text("# Title\nBody", encoding="utf-8")

    command_calls = []

    def fake_run(cmd, **kwargs):
        command_calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stdout="Summary output", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    command_cfg = ["codex", "prompt", "summary", "--file", "{markdown_path}"]
    output_path = summarize.summarize_file(
        markdown,
        tmp_path / "generated",
        command_cfg,
        overwrite=True,
    )

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "Summary output\n"
    assert len(command_calls) == 1
    cmd, kwargs = command_calls[0]
    assert cmd == ["codex", "prompt", "summary", "--file", str(markdown)]
    assert kwargs["input"].startswith("# Title")


def test_main_reports_command_failure(monkeypatch, tmp_path, capsys):
    from src import summarize

    markdown_dir = tmp_path / "data" / "generated"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "example.md").write_text("content", encoding="utf-8")

    def fake_run(_cmd, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="oops")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        summarize,
        "load_config",
        lambda: {"document_ingest": {"summary_command": ["codex", "prompt", "summary"]}},
    )

    rc = summarize.main([
        "--input",
        str(markdown_dir),
        "--output-dir",
        str(tmp_path / "out"),
    ])

    captured = capsys.readouterr()
    assert rc == 1
    assert "oops" in captured.err
