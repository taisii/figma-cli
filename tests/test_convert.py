from pathlib import Path
from types import SimpleNamespace

import pytest

from docling.document_converter import ConversionStatus


@pytest.fixture
def fake_pdf(tmp_path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")
    return pdf_path


def test_convert_single_pdf(monkeypatch, fake_pdf, tmp_path):
    from src import convert

    class DummyDocument:
        def export_to_markdown(self):
            return "# Title\n\nSection paragraph."

    dummy_document = DummyDocument()
    dummy_result = SimpleNamespace(
        status=ConversionStatus.SUCCESS,
        document=dummy_document,
        errors=[],
    )

    class DummyConverter:
        def __init__(self):
            self.paths = []

        def convert(self, path):
            self.paths.append(path)
            return dummy_result

    dummy_converter = DummyConverter()
    monkeypatch.setattr(convert, "_get_converter", lambda: dummy_converter)

    output_dir = tmp_path / "generated"
    md_path = convert.convert_pdf(fake_pdf, output_dir)

    assert dummy_converter.paths == [str(fake_pdf)]
    assert md_path == output_dir / "sample.md"
    content = md_path.read_text(encoding="utf-8")
    assert content.startswith("# Title\n\nSection paragraph.")


def test_convert_refuses_overwrite_without_force(monkeypatch, fake_pdf, tmp_path):
    from src import convert

    def fail_converter():
        raise AssertionError("Docling converter should not be used when overwrite is blocked")

    monkeypatch.setattr(convert, "_get_converter", fail_converter)

    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    existing = output_dir / "sample.md"
    existing.write_text("existing content", encoding="utf-8")

    with pytest.raises(convert.ConversionError):
        convert.convert_pdf(fake_pdf, output_dir)


def test_convert_all_from_directory(monkeypatch, tmp_path):
    from src import convert

    pdf_dir = tmp_path / "data" / "raw" / "papers"
    pdf_dir.mkdir(parents=True)
    first_pdf = pdf_dir / "first.pdf"
    second_pdf = pdf_dir / "second.pdf"
    first_pdf.write_bytes(b"%PDF-1.4 A")
    second_pdf.write_bytes(b"%PDF-1.4 B")

    generated_dir = tmp_path / "data" / "generated"

    calls = []

    def fake_convert(pdf_path, output_dir, force=False):
        calls.append((Path(pdf_path), Path(output_dir), force))
        return Path(output_dir) / (Path(pdf_path).stem + ".md")

    monkeypatch.setattr(convert, "convert_pdf", fake_convert)

    monkeypatch.chdir(tmp_path)

    exit_code = convert.main([])

    assert exit_code == 0
    assert calls == [
        (first_pdf, generated_dir, False),
        (second_pdf, generated_dir, False),
    ]
