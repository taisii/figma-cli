"""PDF 変換ユーティリティ (Docling ベース)。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from docling.document_converter import ConversionStatus, DocumentConverter


DEFAULT_INPUT_DIR = Path("data/input")
DEFAULT_OUTPUT_DIR = Path("data/generated")


class ConversionError(Exception):
    """PDF 変換に失敗した場合の例外。"""


_DOC_CONVERTER: Optional[DocumentConverter] = None


def _get_converter() -> DocumentConverter:
    global _DOC_CONVERTER
    if _DOC_CONVERTER is None:
        _DOC_CONVERTER = DocumentConverter()
    return _DOC_CONVERTER


def convert_pdf(pdf_path: Path, output_dir: Path, *, force: bool = False) -> Path:
    """単一の PDF を Markdown に変換する。"""

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.exists():
        raise ConversionError(f"PDF が見つかりません: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ConversionError(".pdf 以外のファイルは処理できません。")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (pdf_path.stem + ".md")

    if output_path.exists() and not force:
        raise ConversionError(f"出力ファイルが既に存在します: {output_path}")

    markdown = _convert_with_docling(pdf_path)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def _convert_with_docling(pdf_path: Path) -> str:
    converter = _get_converter()
    try:
        result = converter.convert(str(pdf_path))
    except Exception as exc:  # pragma: no cover - 外部ライブラリ例外をまとめて扱う
        raise ConversionError(f"Docling の変換に失敗しました: {exc}") from exc

    if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
        errors = ", ".join(err.error_message for err in getattr(result, "errors", []) if err.error_message)
        error_msg = errors or "詳細不明"
        raise ConversionError(f"Docling が変換に失敗しました: {error_msg}")

    document = getattr(result, "document", None)
    if document is None:
        raise ConversionError("Docling 変換結果に document が含まれていません。")

    markdown = document.export_to_markdown()
    if not markdown.strip():
        raise ConversionError("Docling 変換で空の Markdown が生成されました。")

    return markdown


def _resolve_inputs(inputs: Optional[Sequence[str]]) -> List[Path]:
    if not inputs:
        return _collect_pdfs(DEFAULT_INPUT_DIR)

    collected: List[Path] = []
    seen = set()
    for item in inputs:
        path = Path(item).expanduser()
        if path.is_dir():
            for pdf_path in _collect_pdfs(path):
                if pdf_path not in seen:
                    collected.append(pdf_path)
                    seen.add(pdf_path)
            continue

        if path.suffix.lower() != ".pdf":
            raise ConversionError(f"PDF ファイルではありません: {path}")
        if not path.exists():
            raise ConversionError(f"PDF が見つかりません: {path}")
        resolved = path.resolve()
        if resolved not in seen:
            collected.append(resolved)
            seen.add(resolved)

    if not collected:
        raise ConversionError("処理対象の PDF が見つかりませんでした。")

    return collected


def _collect_pdfs(directory: Path) -> List[Path]:
    directory = Path(directory)
    if not directory.exists():
        raise ConversionError(f"入力ディレクトリが見つかりません: {directory}")
    pdfs = sorted(p.resolve() for p in directory.glob("*.pdf") if p.is_file())
    if not pdfs:
        raise ConversionError(f"PDF が存在しません: {directory}")
    return pdfs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PDF を Markdown に変換するユーティリティ")
    parser.add_argument(
        "--input",
        nargs="*",
        help="処理する PDF ファイルまたはディレクトリ。省略時は data/input 内の全 PDF を対象",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="出力先ディレクトリ (既定: data/generated)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存の Markdown を上書きする",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        output_dir = Path(args.output_dir).expanduser()
        output_dir = output_dir.resolve()
        pdf_paths = _resolve_inputs(args.input)
        for pdf_path in pdf_paths:
            convert_pdf(pdf_path, output_dir, force=args.force)
        return 0
    except ConversionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # 予期しない例外も標準エラーに出す
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
