from pathlib import Path
import json
import yaml


def build_config(tmp_path: Path) -> dict:
    return {
        "document_ingest": {
            "raw_dir": str(tmp_path / "raw"),
            "processed_dir": str(tmp_path / "processed"),
            "summaries_dir": str(tmp_path / "summaries" / "papers"),
            "summary_index_path": str(tmp_path / "summaries" / "papers" / "index.json"),
            "index_path": str(tmp_path / "processed" / "index.yaml"),
        }
    }


def prepare_paper(tmp_path: Path, slug: str, with_meta: bool = True) -> Path:
    root = tmp_path / "processed" / slug
    root.mkdir(parents=True)
    (root / "paper.md").write_text(
        "---\ntitle: Sample Title\nauthors: [Alice, Bob]\nyear: 2024\n---\n\nBody\n",
        encoding="utf-8",
    )
    if with_meta:
        yaml.safe_dump(
            {"id": slug, "title": "Sample Title", "authors": ["Alice", "Bob"], "year": 2024},
            (root / "metadata.yaml").open("w", encoding="utf-8"),
            allow_unicode=True,
            sort_keys=False,
        )
    return root


def test_list_load_and_save_summary(monkeypatch, tmp_path):
    from src.tools import research

    cfg = build_config(tmp_path)
    prepare_paper(tmp_path, "paper-1", with_meta=True)

    # list_papers
    entries = research.list_papers(cfg)
    assert len(entries) == 1
    assert entries[0]["id"] == "paper-1"
    assert entries[0]["title"] == "Sample Title"

    # load_paper
    loaded = research.load_paper("paper-1", max_chars=10, config=cfg)
    assert loaded["truncated"] is True
    assert loaded["content"]

    # save_summary
    result = research.save_summary("paper-1", "Summary text", tags=["tag1"], config=cfg)
    summary_path = Path(result["summary_path"])  # absolute
    alias_path = Path(result["summary_alias_path"])  # absolute
    assert summary_path.exists()
    assert alias_path.exists()
    assert summary_path.read_text(encoding="utf-8").strip() == "Summary text"

    # index.yaml 更新
    index_path = Path(cfg["document_ingest"]["index_path"])
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert any(item["id"] == "paper-1" and item.get("summary_generated") for item in index)

    # summaries index 更新
    sidx_path = Path(cfg["document_ingest"]["summary_index_path"])
    sidx = json.loads(sidx_path.read_text(encoding="utf-8"))
    assert any(item["id"] == "paper-1" for item in sidx)


def test_list_papers_fallback_to_frontmatter_when_metadata_incomplete(tmp_path):
    from src.tools import research

    cfg = build_config(tmp_path)
    root = prepare_paper(tmp_path, "paper-2", with_meta=False)
    # metadata.yaml は id と title のみ（authors/year 欠落）
    (root / "metadata.yaml").write_text(
        yaml.safe_dump({"id": "paper-2", "title": "Sample Title"}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    entries = research.list_papers(cfg)
    e = next(e for e in entries if e["id"] == "paper-2")
    assert e["authors"] == ["Alice", "Bob"]  # frontmatter から補完
    assert e["year"] == 2024


def test_list_papers_prefers_metadata_over_frontmatter(tmp_path):
    from src.tools import research

    cfg = build_config(tmp_path)
    root = prepare_paper(tmp_path, "paper-3", with_meta=False)
    # metadata.yaml に authors/year を明示（meta を優先）
    (root / "metadata.yaml").write_text(
        yaml.safe_dump(
            {"id": "paper-3", "title": "Sample Title", "authors": ["X", "Y"], "year": 1999},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    entries = research.list_papers(cfg)
    e = next(e for e in entries if e["id"] == "paper-3")
    assert e["authors"] == ["X", "Y"]
    assert e["year"] == 1999
