from pathlib import Path
import json


def test_chunk_markdown_heading_strategy(tmp_path):
    from src.tools import research

    markdown_path = tmp_path / "main.md"
    markdown_path.write_text(
        "---\ntitle: Sample\n---\n\n# Intro\nIntro text\n\n## Detail\nMore details here.\n\n# Conclusion\nEnd.",
        encoding="utf-8",
    )

    chunks_dir = tmp_path / "chunks"
    result = research.chunk_markdown_for_llm(
        markdown_path,
        chunks_dir,
        strategy="heading",
        max_chars=50,
        overlap=10,
    )

    index_path = Path(result["index_path"])
    assert index_path.exists()

    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["version"] == 1
    assert index["strategy"] == "heading"
    assert len(index["chunks"]) >= 2

    chunk_paths = [Path(chunk["path"]) for chunk in result["chunks"]]
    for chunk_path in chunk_paths:
        assert chunk_path.exists()
        assert chunk_path.read_text(encoding="utf-8").strip()


def test_chunk_markdown_fixed_strategy(tmp_path):
    from src.tools import research

    markdown_path = tmp_path / "main.md"
    markdown_path.write_text("Simple content that should be split.", encoding="utf-8")

    chunks_dir = tmp_path / "fixed"
    result = research.chunk_markdown_for_llm(
        markdown_path,
        chunks_dir,
        strategy="fixed",
        max_chars=10,
        overlap=2,
    )

    assert len(result["chunks"]) > 1
    first_chunk = Path(result["chunks"][0]["path"]).read_text(encoding="utf-8")
    assert first_chunk.strip().startswith("Simple")
