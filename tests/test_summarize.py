from pathlib import Path

import pytest


def test_summarize_skips_without_api_key(monkeypatch, tmp_path):
    from src import summarize

    paper = tmp_path / "paper.md"
    paper.write_text("# Title\nBody", encoding="utf-8")

    monkeypatch.setattr(summarize, "load_config", lambda: {"gemini_model_name": "dummy-model"})
    monkeypatch.delenv("AI_API_KEY", raising=False)

    exit_code = summarize.main([
        "--input",
        str(paper),
        "--output-dir",
        str(tmp_path / "generated"),
    ])

    assert exit_code == 0
    assert not (tmp_path / "generated" / "paper_summary.md").exists()


def test_summarize_creates_summary(monkeypatch, tmp_path):
    from src import summarize

    paper = tmp_path / "notes.md"
    paper.write_text("Some findings.", encoding="utf-8")

    monkeypatch.setattr(summarize, "load_config", lambda: {"gemini_model_name": "dummy-model"})
    monkeypatch.setenv("AI_API_KEY", "test-key")

    prompts = []

    class DummyResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class DummyModel:
        def generate_content(self, prompt: str):
            prompts.append(prompt)
            return DummyResponse("Summary output")

    monkeypatch.setattr(summarize, "build_generative_model", lambda config, model_name_override=None: DummyModel())
    monkeypatch.setattr(summarize, "current_timestamp", lambda: "2025-01-01T00:00:00+00:00")

    exit_code = summarize.main([
        "--input",
        str(paper),
        "--output-dir",
        str(tmp_path / "generated"),
    ])

    assert exit_code == 0
    assert len(prompts) == 1

    summary_path = tmp_path / "generated" / "notes_summary.md"
    content = summary_path.read_text(encoding="utf-8")
    assert content.startswith("generated_at: 2025-01-01T00:00:00+00:00\n\nSummary output")
