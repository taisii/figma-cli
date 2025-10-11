from __future__ import annotations

import json
from pathlib import Path

import yaml


def test_ingest_list_load_and_save_summary(monkeypatch, tmp_path):
    from src.tools import research
    from src import convert

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    def fake_convert(pdf, out_dir, options=None):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = out_dir / "assets"
        tables_dir = out_dir / "tables"
        assets_dir.mkdir(exist_ok=True)
        tables_dir.mkdir(exist_ok=True)
        main_md = out_dir / "main.md"
        main_md.write_text("# Sample Paper\n\nThis is the content.", encoding="utf-8")
        return {
            "main_md_path": str(main_md),
            "assets_dir": str(assets_dir),
            "tables_dir": str(tables_dir),
            "page_map": [{"page": 1, "start": 0, "end": 10}],
            "pdf_sha256": "sha256-pdf",
            "docling_opts_sha256": "sha256-opts",
        }

    monkeypatch.setattr(convert, "convert_pdf_to_markdown", fake_convert)

    base_dir = tmp_path
    result = research.ingest_pdf("sample-paper", pdf_path, base_dir)

    main_md_path = Path(result["main_md_path"])
    assert main_md_path.exists()
    assert main_md_path.read_text(encoding="utf-8").startswith("---\n")

    papers_index = base_dir / "context" / "papers" / "index.yaml"
    index_data = yaml.safe_load(papers_index.read_text(encoding="utf-8"))
    assert index_data["version"] == 1
    paper_entry = next(item for item in index_data["papers"] if item["slug"] == "sample-paper")
    assert paper_entry["chunk_count"] == len(result["chunks"])
    assert paper_entry["hash"]["pdf_sha256"] == "sha256-pdf"

    entries = research.list_papers(base_dir)
    assert len(entries) == 1
    assert entries[0]["slug"] == "sample-paper"
    assert Path(entries[0]["md_path"]).exists()

    loaded = research.load_paper("sample-paper", base_dir, max_chars=50)
    assert loaded["meta"]["title"] == "Sample Paper"
    assert loaded["truncated"] is False

    summary_result = research.save_summary("sample-paper", "Summary text", base_dir, tags=["intro"])
    summary_path = Path(summary_result["summary_path"])
    assert summary_path.exists()
    assert summary_path.read_text(encoding="utf-8").strip().endswith("Summary text")

    summary_index_path = base_dir / "context" / "summaries" / "papers" / "index.json"
    summary_index = json.loads(summary_index_path.read_text(encoding="utf-8"))
    assert summary_index["version"] == 1
    summary_entry = summary_index["summaries"][0]
    assert summary_entry["slug"] == "sample-paper"
    assert summary_entry["tags"] == ["intro"]
    assert summary_entry["source_hash"] == "sha256-pdf"
    assert summary_entry["chunk_refs"] == [chunk["id"] for chunk in result["chunks"]]
