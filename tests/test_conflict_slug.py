from pathlib import Path

import pytest


def test_ingest_conflict_slug_raises(monkeypatch, tmp_path: Path):
    from src.tools import research
    from src import convert

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    def fake_convert(pdf, out_dir, options=None):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "assets").mkdir(exist_ok=True)
        (out_dir / "tables").mkdir(exist_ok=True)
        main_md = out_dir / "main.md"
        main_md.write_text("# Title\n\nBody.", encoding="utf-8")
        return {
            "main_md_path": str(main_md),
            "assets_dir": str(out_dir / "assets"),
            "tables_dir": str(out_dir / "tables"),
            "page_map": [{"page": 1, "start": 0, "end": 6}],
            "pdf_sha256": "sha256-pdf",
            "docling_opts_sha256": "sha256-opts",
        }

    monkeypatch.setattr(convert, "convert_pdf_to_markdown", fake_convert)

    base_dir = tmp_path
    slug = "conflict-test"

    # 1回目は成功
    research.ingest_pdf(slug, pdf_path, base_dir)

    # 2回目は ConflictError
    with pytest.raises(research.ConflictError):
        research.ingest_pdf(slug, pdf_path, base_dir)

