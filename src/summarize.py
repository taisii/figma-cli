"""サマリー生成コマンドのコア実装。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import dotenv
import yaml

from .llm_client import LLMUnavailableError, build_generative_model


DEFAULT_INPUT_DIR = Path("data/generated")
DEFAULT_OUTPUT_DIR = Path("data/generated")


class SummarizeError(Exception):
    """サマリー生成全般の例外。"""


def load_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def summarize_markdown(markdown_text: str, model) -> str:
    prompt = (
        "You are a research collaborator. Produce a concise summary covering objectives, "
        "methods, key findings, and open questions of the following paper."
    )
    response = model.generate_content([prompt, markdown_text])
    summary_text = getattr(response, "text", "").strip()
    if not summary_text:
        raise SummarizeError("LLM からサマリー本文を取得できませんでした。")

    return _format_summary(summary_text)


def _format_summary(summary_text: str) -> str:
    timestamp = current_timestamp()
    body = summary_text.strip()
    return f"generated_at: {timestamp}\n\n{body}\n"


def summarize_file(markdown_path: Path, output_dir: Path, model, *, force: bool = True) -> Path:
    markdown_path = Path(markdown_path)
    output_dir = Path(output_dir)

    if not markdown_path.exists():
        raise SummarizeError(f"Markdown が見つかりません: {markdown_path}")
    if markdown_path.suffix.lower() != ".md":
        raise SummarizeError(f".md ファイルのみ処理可能です: {markdown_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{markdown_path.stem}_summary.md"
    if output_path.exists() and not force:
        raise SummarizeError(f"既にサマリーが存在します: {output_path}")

    markdown_text = markdown_path.read_text(encoding="utf-8")
    summary = summarize_markdown(markdown_text, model)
    output_path.write_text(summary, encoding="utf-8")
    return output_path


def _resolve_inputs(values: Optional[Sequence[str]]) -> List[Path]:
    if not values:
        return _collect_markdown(DEFAULT_INPUT_DIR)

    collected: List[Path] = []
    seen = set()
    for value in values:
        path = Path(value).expanduser()
        if path.is_dir():
            for md_path in _collect_markdown(path):
                if md_path not in seen:
                    collected.append(md_path)
                    seen.add(md_path)
            continue

        if path.suffix.lower() != ".md":
            raise SummarizeError(f"Markdown ファイルではありません: {path}")
        if not path.exists():
            raise SummarizeError(f"Markdown が見つかりません: {path}")
        resolved = path.resolve()
        if resolved not in seen:
            collected.append(resolved)
            seen.add(resolved)

    if not collected:
        raise SummarizeError("処理対象の Markdown が見つかりませんでした。")
    return collected


def _collect_markdown(directory: Path) -> List[Path]:
    directory = Path(directory)
    if not directory.exists():
        raise SummarizeError(f"入力ディレクトリが見つかりません: {directory}")
    markdown_files = sorted(
        p.resolve()
        for p in directory.glob("*.md")
        if p.is_file() and not p.name.endswith("_summary.md") and p.name != "conversation_log.md"
    )
    if not markdown_files:
        raise SummarizeError(f"Markdown ファイルが存在しません: {directory}")
    return markdown_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Markdown を要約するユーティリティ")
    parser.add_argument(
        "--input",
        nargs="*",
        help="サマリー生成対象の Markdown ファイルまたはディレクトリ。省略時は data/generated 配下",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="サマリー出力先 (既定: data/generated)",
    )
    parser.add_argument(
        "--model",
        help="Gemini モデル ID の上書き値",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="既存サマリーファイルを保持する",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config()
    dotenv.load_dotenv()

    if not os.getenv("AI_API_KEY"):
        print("Warning: AI_API_KEY が未設定のためサマリー生成をスキップします。", file=sys.stderr)
        return 0

    try:
        markdown_paths = _resolve_inputs(args.input)
        output_dir = Path(args.output_dir).expanduser().resolve()
        model = build_generative_model(config, model_name_override=args.model)
        for path in markdown_paths:
            summarize_file(path, output_dir, model, force=not args.no_overwrite)
        return 0
    except LLMUnavailableError as exc:
        message = str(exc)
        if "AI_API_KEY" in message:
            print(f"Warning: {message}", file=sys.stderr)
            return 0
        print(f"Error: {message}", file=sys.stderr)
        return 1
    except SummarizeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # 予期しない例外
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
