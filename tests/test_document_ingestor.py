from pathlib import Path

import pytest
import yaml
from pypdf import PdfWriter

from src.document_ingestor import DocumentIngestor, DocumentIngestionError


def build_config(tmp_path: Path) -> dict:
    return {
        "document_ingest": {
            "raw_dir": str(tmp_path / "raw"),
            "processed_dir": str(tmp_path / "processed"),
            "index_path": str(tmp_path / "index.yaml"),
        }
    }


def test_ingest_tex_folder_creates_artifacts(monkeypatch, tmp_path):
    config = build_config(tmp_path)
    ingestor = DocumentIngestor(config)

    def fake_which(cmd: str):
        import shutil as _shutil

        if cmd in {"latexpand", "pandoc"}:
            return None
        return _shutil.which(cmd)

    import src.document_ingestor as di_module

    monkeypatch.setattr(di_module.shutil, "which", fake_which)

    project_dir = tmp_path / "texproj"
    project_dir.mkdir()
    tex_content = r"""
\documentclass{article}
\title{Sample Document}
\author{Alice \and Bob}
\date{2024}
\newcommand{\R}{\mathbb{R}}
\begin{document}
\maketitle
\section{Introduction}
This is the introduction.
\section{Method}
Details go here.
\end{document}
"""
    (project_dir / "main.tex").write_text(tex_content, encoding="utf-8")

    result = ingestor.ingest_tex_folder(project_dir, copy_to_raw=False)

    assert result.slug.startswith("2024-sample-document")
    paper = result.paper_path
    metadata_path = result.metadata_path
    macros_path = paper.parent / "macros.md"
    chunks_path = paper.parent / "chunks.yaml"

    assert paper.exists()
    assert metadata_path.exists()
    assert macros_path.exists()
    assert chunks_path.exists()

    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_type"] == "tex"
    assert metadata["title"] == "Sample Document"
    assert metadata["authors"] == ["Alice", "Bob"]

    macros_md = macros_path.read_text(encoding="utf-8")
    assert "\\newcommand{\\R}{\\mathbb{R}}" in macros_md

    chunks = yaml.safe_load(chunks_path.read_text(encoding="utf-8"))
    assert len(chunks) >= 1
    assert chunks[0]["path"].endswith("00.md")


def test_ingest_tex_folder_skips_existing(monkeypatch, tmp_path):
    config = build_config(tmp_path)
    ingestor = DocumentIngestor(config)

    project_dir = tmp_path / "texproj"
    project_dir.mkdir()
    tex_path = project_dir / "main.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")

    ingestor.ingest_tex_folder(project_dir, copy_to_raw=False)

    convert_called = False

    def fake_convert(self, expanded_tex):
        nonlocal convert_called
        convert_called = True
        return "markdown"

    monkeypatch.setattr(DocumentIngestor, "_convert_tex_to_markdown", fake_convert)

    result = ingestor.ingest_tex_folder(project_dir, copy_to_raw=False)

    assert not convert_called
    assert "Skipped" in result.message


def test_ingest_pdf_creates_markdown(tmp_path):
    config = build_config(tmp_path)
    ingestor = DocumentIngestor(config)

    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": "Sample PDF", "/Author": "Carol"})
    with pdf_path.open("wb") as handle:
        writer.write(handle)

    result = ingestor.ingest_pdf(pdf_path, copy_to_raw=False)

    paper_md = result.paper_path.read_text(encoding="utf-8")
    assert "Sample PDF" in paper_md
    metadata = yaml.safe_load(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_type"] == "pdf"
    assert metadata["title"] == "Sample PDF"


def test_ingest_nonexistent_tex_folder(tmp_path):
    config = build_config(tmp_path)
    ingestor = DocumentIngestor(config)

    with pytest.raises(DocumentIngestionError):
        ingestor.ingest_tex_folder(tmp_path / "missing", copy_to_raw=False)
