"""Codex プロンプトを用いて Markdown サマリーを生成するユーティリティ。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

import yaml

DEFAULT_INPUT_DIR = Path("data/generated")
DEFAULT_OUTPUT_DIR = Path("data/generated")


class SummarizeError(Exception):
    """サマリー生成時の利用者向け例外。"""


def load_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}


def _summary_command(config: dict) -> List[str]:
    ingestion_cfg = config.get("document_ingest") or {}
    command_value = ingestion_cfg.get("summary_command", ["codex", "prompt", "summary"])
    if isinstance(command_value, str):
        return [command_value]
    return [str(part) for part in command_value]


def _resolve_inputs(values: Optional[Sequence[str]]) -> List[Path]:
    if not values:
        return _collect_markdown(DEFAULT_INPUT_DIR)

    collected: List[Path] = []
    seen = set()
    for value in values:
        path = Path(value).expanduser()
        if path.is_dir():
            for candidate in _collect_markdown(path):
                if candidate not in seen:
                    collected.append(candidate)
                    seen.add(candidate)
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


def _build_command(command_cfg: Sequence[str], *, slug: str, markdown_path: Path) -> List[str]:
    return [
        str(part).format(
            slug=slug,
            paper_path=str(markdown_path),
            markdown_path=str(markdown_path),
        )
        for part in command_cfg
    ]


def summarize_file(
    markdown_path: Path,
    output_dir: Path,
    command_cfg: Sequence[str],
    *,
    overwrite: bool,
) -> Path:
    markdown_path = Path(markdown_path)
    output_dir = Path(output_dir)

    if not markdown_path.exists():
        raise SummarizeError(f"Markdown が見つかりません: {markdown_path}")
    if markdown_path.suffix.lower() != ".md":
        raise SummarizeError(f".md ファイルのみ処理可能です: {markdown_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{markdown_path.stem}_summary.md"
    if output_path.exists() and not overwrite:
        raise SummarizeError(f"既にサマリーが存在します: {output_path}")

    try:
        markdown_text = markdown_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SummarizeError(f"Markdown の読み込みに失敗しました: {exc}") from exc

    command = _build_command(command_cfg, slug=markdown_path.stem, markdown_path=markdown_path)

    env = os.environ.copy()
    env.setdefault("CODEX_SUMMARY_SLUG", markdown_path.stem)
    env.setdefault("CODEX_SUMMARY_TITLE", markdown_path.stem)

    try:
        result = subprocess.run(
            command,
            input=markdown_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        raise SummarizeError(f"サマリーコマンドが見つかりません: {command[0]}") from exc
    except Exception as exc:  # pragma: no cover - 想定外のエラー
        raise SummarizeError(f"サマリーコマンドの実行に失敗しました: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise SummarizeError(
            f"サマリーコマンドが異常終了しました (exit={result.returncode}): {stderr}"
        )

    summary_text = (result.stdout or "").strip()
    if not summary_text:
        raise SummarizeError("サマリーコマンドが空の出力を返しました。")

    output_path.write_text(summary_text + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex プロンプトで Markdown を要約するユーティリティ")
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
        "--no-overwrite",
        action="store_true",
        help="既存サマリーファイルを保持する",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
        command_cfg = _summary_command(config)
        markdown_paths = _resolve_inputs(args.input)
        output_dir = Path(args.output_dir).expanduser().resolve()

        for path in markdown_paths:
            summarize_file(path, output_dir, command_cfg, overwrite=not args.no_overwrite)
        return 0
    except SummarizeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - 予期しない例外
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
