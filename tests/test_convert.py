from pathlib import Path
from types import SimpleNamespace

import hashlib

import pytest

from docling.document_converter import ConversionStatus


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")
    return pdf_path


def test_convert_pdf_to_markdown(monkeypatch, fake_pdf, tmp_path):
    from src import convert

    markdown_text = "# Sample Paper\n\nBody paragraph."
    page_map = [
        {"page": 1, "start": 0, "end": len(markdown_text)},
    ]

    dummy_document = SimpleNamespace(export_to_markdown=lambda: markdown_text)
    dummy_result = SimpleNamespace(
        status=ConversionStatus.SUCCESS,
        document=dummy_document,
        errors=[],
        page_map=page_map,
    )

    class DummyConverter:
        def __init__(self):
            self.paths = []

        def convert(self, path):
            self.paths.append(path)
            return dummy_result

    dummy_converter = DummyConverter()
    monkeypatch.setattr(convert, "_get_converter", lambda: dummy_converter)

    options = {"mode": "fast"}
    out_dir = tmp_path / "output"
    result = convert.convert_pdf_to_markdown(fake_pdf, out_dir, options=options)

    expected_hash = hashlib.sha256(fake_pdf.read_bytes()).hexdigest()
    expected_opts_hash = hashlib.sha256(b'{"mode": "fast"}').hexdigest()

    main_md_path = Path(result["main_md_path"])
    assert main_md_path.exists()
    assert main_md_path.read_text(encoding="utf-8") == markdown_text

    assert result["assets_dir"] == str(out_dir / "assets")
    assert result["tables_dir"] == str(out_dir / "tables")
    assert result["page_map"] == page_map
    assert result["pdf_sha256"] == expected_hash
    assert result["docling_opts_sha256"] == expected_opts_hash

    # converter が呼ばれた
    assert dummy_converter.paths == [str(fake_pdf)]
