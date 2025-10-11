from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def prepare_paper_with_invalid_frontmatter(base_dir: Path, slug: str) -> None:
    paper_dir = base_dir / "context" / "papers" / slug
    paper_dir.mkdir(parents=True, exist_ok=True)
    # Invalid YAML front matter (unterminated list)
    paper_dir.joinpath("main.md").write_text(
        "---\nauthors: [\n---\ncontent\n",
        encoding="utf-8",
    )

    chunks_dir = paper_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_path = chunks_dir / "0001.md"
    chunk_path.write_text("Chunk", encoding="utf-8")
    index = {
        "version": 1,
        "strategy": "heading",
        "max_chars": 4000,
        "overlap": 200,
        "chunks": [{"id": "0001", "path": str(chunk_path)}],
    }
    chunks_dir.joinpath("index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    papers_index = base_dir / "context" / "papers"
    papers_index.mkdir(parents=True, exist_ok=True)
    yaml.safe_dump(
        {
            "version": 1,
            "papers": [
                {
                    "slug": slug,
                    "title": slug,
                    "md_path": str(Path("context") / "papers" / slug / "main.md"),
                    "assets_dir": str(Path("context") / "papers" / slug / "assets"),
                    "tables_dir": str(Path("context") / "papers" / slug / "tables"),
                    "chunk_index_path": str(Path("context") / "papers" / slug / "chunks" / "index.json"),
                    "chunk_count": 1,
                    "pages": 1,
                    "hash": {"pdf_sha256": "hash", "docling_opts": "opts"},
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ],
        },
        (papers_index / "index.yaml").open("w", encoding="utf-8"),
        allow_unicode=True,
        sort_keys=False,
    )


def test_save_summary_raises_on_bad_frontmatter(tmp_path: Path):
    from src.tools import research

    slug = "bad-paper"
    prepare_paper_with_invalid_frontmatter(tmp_path, slug)

    with pytest.raises(yaml.YAMLError):
        research.save_summary(slug, "summary", tmp_path)

    summary_path = tmp_path / "context" / "summaries" / "papers" / f"{slug}.md"
    assert not summary_path.exists()
