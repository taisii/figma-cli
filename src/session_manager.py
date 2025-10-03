"""対話セッションを管理するシンプルな CLI ラッパー。"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import dotenv
import yaml

from .llm_client import LLMUnavailableError, build_generative_model


DEFAULT_KNOWLEDGE_DIR = Path("data/generated")
CONVERSATION_LOG_NAME = "conversation_log.md"
REQUIRED_CODEX_VERSION = (0, 5, 0)


class SessionCommandError(Exception):
    """セッション操作時の利用者向け例外。"""


@dataclass
class ListEntry:
    name: str
    path: Path
    missing_summary: bool = False
    mtime: float = field(repr=False, compare=False, default=0.0)


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}


class SessionManager:
    """知識ベースと会話ログを扱うユーティリティクラス。"""

    def __init__(self, knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR, *, model=None) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        self.conversation_log_path = self.knowledge_dir / CONVERSATION_LOG_NAME
        self._ensure_conversation_log()

        self.model = model
        self.active_documents: List[Path] = []
        self.messages: List[str] = []

    # ------------------------------------------------------------------
    # 基本操作

    def _ensure_conversation_log(self) -> None:
        if self.conversation_log_path.exists():
            return
        timestamp = current_timestamp()
        self.conversation_log_path.write_text(
            f"{timestamp} session initialized\n", encoding="utf-8"
        )

    def list_documents(self) -> List[ListEntry]:
        entries: List[ListEntry] = []

        for summary_path in self.knowledge_dir.glob("*_summary.md"):
            if not summary_path.is_file():
                continue
            entries.append(
                ListEntry(
                    name=summary_path.name,
                    path=summary_path.resolve(),
                    missing_summary=False,
                    mtime=summary_path.stat().st_mtime,
                )
            )

        for paper_path in self.knowledge_dir.glob("*.md"):
            if paper_path.name.endswith("_summary.md") or paper_path.name == CONVERSATION_LOG_NAME:
                continue
            partner = paper_path.with_name(f"{paper_path.stem}_summary.md")
            if not partner.exists():
                entries.append(
                    ListEntry(
                        name=f"{paper_path.name} (summary missing)",
                        path=paper_path.resolve(),
                        missing_summary=True,
                        mtime=paper_path.stat().st_mtime,
                    )
                )

        entries.sort(key=lambda item: item.mtime, reverse=True)
        return entries

    def load_document(self, filename: str) -> Path:
        target = (self.knowledge_dir / filename).resolve()
        if not target.exists() or not target.is_file():
            raise SessionCommandError(f"ファイルが見つかりません: {filename}")
        if target.name == CONVERSATION_LOG_NAME:
            raise SessionCommandError("conversation_log.md はロード対象外です。")
        if target not in self.active_documents:
            self.active_documents.append(target)
        return target

    def reset_context(self) -> None:
        self.active_documents.clear()

    def record_user_message(self, message: str) -> None:
        text = message.strip()
        if text:
            self.messages.append(text)

    def generate_session_summary(self) -> str:
        if not self.messages:
            raise SessionCommandError("要約対象の会話がありません。")
        if self.model is None:
            raise SessionCommandError("LLM モデルが未設定です。")

        conversation = "\n".join(self.messages)
        prompt = (
            "You are a research collaborator. Summarize the following conversation into "
            "actionable research notes."
        )
        response = self.model.generate_content([prompt, conversation])
        summary_text = getattr(response, "text", "").strip()
        if not summary_text:
            raise SessionCommandError("LLM が空のサマリーを返しました。")

        timestamp = current_timestamp()
        block = f"{timestamp} {summary_text}"
        with self.conversation_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{block}\n\n")

        self.messages.clear()
        return block


# ----------------------------------------------------------------------
# CLI 補助


def _parse_version(value: str) -> tuple[int, ...]:
    parts = value.split(".")
    version_parts: List[int] = []
    for part in parts:
        try:
            version_parts.append(int(part))
        except ValueError:
            version_parts.append(0)
    return tuple(version_parts)


def _ensure_codex_cli_version() -> None:
    try:
        import codex_cli as codex_module
    except ImportError as exc:  # pragma: no cover - 実行時のみ
        raise SessionCommandError("Codex CLI が見つかりません。") from exc

    version_str = getattr(codex_module, "__version__", "0.0.0")
    if _parse_version(version_str) < REQUIRED_CODEX_VERSION:
        raise SessionCommandError(
            f"Codex CLI v{version_str} はサポート対象外です。{'.'.join(map(str, REQUIRED_CODEX_VERSION))} 以上に更新してください。"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="研究セッション用 CLI ラッパー")
    parser.add_argument(
        "--knowledge-dir",
        default=str(DEFAULT_KNOWLEDGE_DIR),
        help="知識ベースディレクトリ (既定: data/generated)",
    )
    parser.add_argument(
        "--model",
        help="Gemini モデル ID の上書き値",
    )
    return parser


def _interactive_loop(manager: SessionManager) -> int:
    print("セッション開始: /list, /load <file>, /reset, /summary, /exit を利用できます。")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            break

        if not line:
            continue

        if line.startswith("/"):
            command, *rest = line.split(maxsplit=1)
            argument = rest[0] if rest else ""
            try:
                if command == "/list":
                    entries = manager.list_documents()
                    if not entries:
                        print("知識ベースにサマリーがありません。")
                        continue
                    for entry in entries:
                        marker = " !" if entry.missing_summary else ""
                        print(f"- {entry.name}{marker}")
                elif command == "/load":
                    if not argument:
                        raise SessionCommandError("/load にはファイル名の指定が必要です。")
                    path = manager.load_document(argument)
                    print(f"読み込み完了: {path.name}")
                elif command == "/reset":
                    manager.reset_context()
                    print("コンテキストを初期化しました。")
                elif command == "/summary":
                    block = manager.generate_session_summary()
                    print(f"要約を conversation_log.md に追記しました: {block}")
                elif command in {"/exit", "/quit"}:
                    break
                else:
                    print(f"未対応のコマンドです: {command}")
            except SessionCommandError as exc:
                print(f"Error: {exc}")
            continue

        manager.record_user_message(line)

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dotenv.load_dotenv()

    try:
        _ensure_codex_cli_version()
        if not os.getenv("AI_API_KEY"):
            raise SessionCommandError("AI_API_KEY が設定されていません。")

        knowledge_dir = Path(args.knowledge_dir).expanduser().resolve()
        config = load_config()
        model = build_generative_model(config, model_name_override=args.model)

        manager = SessionManager(knowledge_dir, model=model)
        return _interactive_loop(manager)
    except SessionCommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except LLMUnavailableError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - 想定外の例外
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
