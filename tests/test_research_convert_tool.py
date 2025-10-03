from pathlib import Path


def test_convert_pdf_tool_invokes_convert(monkeypatch, tmp_path):
    from src.tools import research

    calls = []

    def fake_convert(pdf, out_dir, force=False):
        calls.append((pdf, out_dir, force))
        out = out_dir / (pdf.stem + ".md")
        out_dir.mkdir(parents=True, exist_ok=True)
        out.write_text("# MD", encoding="utf-8")
        return out

    # 差し替え
    import src.convert as convert_mod

    monkeypatch.setattr(convert_mod, "convert_pdf", fake_convert)

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    out_dir = tmp_path / "gen"
    res = research.convert_pdf_tool(str(pdf_path), output_dir=str(out_dir), force=True)

    assert Path(res["markdown_path"]).exists()
    assert calls[0][0] == pdf_path.resolve()
    assert calls[0][1] == out_dir.resolve()
    assert calls[0][2] is True

