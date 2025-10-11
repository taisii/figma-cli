"""Docling を用いた PDF→Markdown 変換ユーティリティ。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from docling.document_converter import ConversionStatus, DocumentConverter


class ConvertError(Exception):
    """PDF の変換に失敗した場合の例外。"""


_DOC_CONVERTER: Optional[DocumentConverter] = None


def _get_converter() -> DocumentConverter:
    global _DOC_CONVERTER
    if _DOC_CONVERTER is None:
        _DOC_CONVERTER = DocumentConverter()
    return _DOC_CONVERTER


@dataclass
class ConvertResult:
    main_md_path: Path
    assets_dir: Path
    tables_dir: Path
    page_map: List[Dict[str, Any]]
    pdf_sha256: str
    docling_opts_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "main_md_path": str(self.main_md_path),
            "assets_dir": str(self.assets_dir),
            "tables_dir": str(self.tables_dir),
            "page_map": self.page_map,
            "pdf_sha256": self.pdf_sha256,
            "docling_opts_sha256": self.docling_opts_sha256,
        }


def convert_pdf_to_markdown(
    pdf_path: str | Path,
    out_dir: str | Path,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Docling で PDF を Markdown に変換し、関連ディレクトリを整備する。"""

    pdf = Path(pdf_path)
    if not pdf.exists():
        raise ConvertError(f"PDF not found: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise ConvertError("Only .pdf files can be converted")

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = output_dir / "assets"
    tables_dir = output_dir / "tables"
    assets_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    markdown, page_map = _convert_with_docling(pdf, options or {})

    main_md_path = output_dir / "main.md"
    main_md_path.write_text(markdown, encoding="utf-8")

    pdf_sha = _sha256_file(pdf)
    opts_sha = _sha256_options(options or {})

    result = ConvertResult(
        main_md_path=main_md_path,
        assets_dir=assets_dir,
        tables_dir=tables_dir,
        page_map=page_map,
        pdf_sha256=pdf_sha,
        docling_opts_sha256=opts_sha,
    )
    return result.to_dict()


def _convert_with_docling(
    pdf_path: Path,
    options: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    converter = _get_converter()
    try:
        result = converter.convert(str(pdf_path))
    except Exception as exc:  # pragma: no cover - 外部ライブラリの例外をまとめて扱う
        raise ConvertError(f"Docling convert failed: {exc}") from exc

    if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
        errors: List[str] = []
        for err in getattr(result, "errors", []) or []:
            message = getattr(err, "error_message", None)
            if message:
                errors.append(str(message))
        joined = "; ".join(errors) if errors else "unknown error"
        raise ConvertError(f"Docling returned non-success status: {joined}")

    document = getattr(result, "document", None)
    if document is None:
        raise ConvertError("Docling result is missing document content")

    markdown = document.export_to_markdown()
    if not isinstance(markdown, str) or not markdown.strip():
        raise ConvertError("Docling produced empty markdown output")

    raw_page_map = getattr(result, "page_map", None)
    page_map: List[Dict[str, Any]]
    if isinstance(raw_page_map, list) and raw_page_map:
        page_map = [
            {
                "page": int(item.get("page", index + 1)),
                "start": int(item.get("start", 0)),
                "end": int(item.get("end", 0)),
            }
            for index, item in enumerate(raw_page_map)
        ]
    else:
        page_map = _fallback_page_map(markdown)

    return markdown, page_map


def _fallback_page_map(markdown: str) -> List[Dict[str, int]]:
    text_length = len(markdown)
    return [
        {
            "page": 1,
            "start": 0,
            "end": text_length,
        }
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_options(options: Dict[str, Any]) -> str:
    normalized = json.dumps(options, ensure_ascii=False, sort_keys=True, separators=(",", ": ")).encode(
        "utf-8"
    )
    return hashlib.sha256(normalized).hexdigest()


__all__ = ["convert_pdf_to_markdown", "ConvertError"]
