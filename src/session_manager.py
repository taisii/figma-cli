"""対話セッションを管理するシンプルな CLI ラッパー。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import dotenv
import yaml


DEFAULT_KNOWLEDGE_DIR = Path("context/summaries")
CONVERSATION_LOG_NAME = "conversation_log.md"
REQUIRED_CODEX_VERSION = (0, 5, 0)
DEFAULT_SUMMARY_COMMAND = ["codex", "prompt", "session-summary"]


class SessionCommandError(Exception):
    """セッション操作時の利用者向け例外。"""


@dataclass
class ListEntry:
    name: str
    path: Path
    missing_summary: bool = False
    mtime: float = field(repr=False, compare=False, default=0.0)


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: str


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

    def __init__(
        self,
        knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
        *,
        auto_preload: bool = False,
        preload_limit: Optional[int] = None,
        summary_command: Optional[Sequence[str]] = None,
        summary_env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        self.conversation_log_path = self.knowledge_dir / CONVERSATION_LOG_NAME
        self._ensure_conversation_log()

        self.active_documents: List[Path] = []
        self.messages: List[SessionMessage] = []
        self.summary_command = self._normalize_command(summary_command)
        self.summary_env = dict(summary_env or {})

        if auto_preload:
            self._auto_preload(preload_limit)

    # ------------------------------------------------------------------
    # 基本操作

    def _ensure_conversation_log(self) -> None:
        if self.conversation_log_path.exists():
            return
        timestamp = current_timestamp()
        self.conversation_log_path.write_text(
            f"{timestamp} session initialized\n", encoding="utf-8"
        )

    def _auto_preload(self, preload_limit: Optional[int]) -> None:
        summaries = [
            path
            for path in self.knowledge_dir.glob("*.md")
            if path.name != CONVERSATION_LOG_NAME and path.is_file()
        ]
        summaries.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        if preload_limit is not None and preload_limit >= 0:
            summaries = summaries[: preload_limit]
        self.active_documents = summaries

    @staticmethod
    def _normalize_command(command: Optional[Sequence[str]]) -> List[str]:
        if command is None:
            return list(DEFAULT_SUMMARY_COMMAND)
        if isinstance(command, (list, tuple)):
            normalized = [str(part) for part in command if str(part).strip()]
        else:
            value = str(command).strip()
            normalized = [value] if value else []
        return normalized

    def _build_prompt_payload(self) -> str:
        lines = ["# Conversation Log"]
        for message in self.messages:
            content = message.content.replace("\r\n", "\n").strip()
            if not content:
                continue
            first_line, *rest = content.splitlines()
            lines.append(f"- [{message.timestamp}] {message.role}: {first_line}")
            for line in rest:
                lines.append(f"  {line.strip()}")
        if len(lines) == 1:
            raise SessionCommandError("要約対象の会話がありません。")

        if self.active_documents:
            lines.append("")
            lines.append("# Active Summaries")
            for path in self.active_documents:
                lines.append(f"- {path.name}")

        return "\n".join(lines)

    def _build_subprocess_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env.update(self.summary_env)
        env.setdefault("CODEX_SESSION_KNOWLEDGE_DIR", str(self.knowledge_dir))
        env.setdefault("CODEX_SESSION_LOG_PATH", str(self.conversation_log_path))
        env.setdefault("CODEX_SESSION_MESSAGE_COUNT", str(len(self.messages)))
        if self.active_documents:
            active = ",".join(sorted(path.name for path in self.active_documents))
            env.setdefault("CODEX_SESSION_ACTIVE_DOCUMENTS", active)
        return env

    def list_documents(self) -> List[ListEntry]:
        entries: List[ListEntry] = []
        for summary_path in self.knowledge_dir.glob("*.md"):
            if summary_path.name == CONVERSATION_LOG_NAME or not summary_path.is_file():
                continue
            entries.append(
                ListEntry(
                    name=summary_path.name,
                    path=summary_path.resolve(),
                    missing_summary=False,
                    mtime=summary_path.stat().st_mtime,
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
            self.messages.append(
                SessionMessage(role="USER", content=text, timestamp=current_timestamp())
            )

    def record_assistant_message(self, message: str) -> None:
        text = message.strip()
        if text:
            self.messages.append(
                SessionMessage(role="ASSISTANT", content=text, timestamp=current_timestamp())
            )

    def generate_session_summary(self) -> str:
        if not self.messages:
            raise SessionCommandError("要約対象の会話がありません。")
        if not self.summary_command:
            raise SessionCommandError("要約コマンドが未設定です。")

        payload = self._build_prompt_payload()
        env = self._build_subprocess_env()

        try:
            result = subprocess.run(
                self.summary_command,
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise SessionCommandError(
                f"要約コマンドが見つかりません: {self.summary_command[0]}"
            ) from exc
        except Exception as exc:  # pragma: no cover - subprocess の予期しない失敗
            raise SessionCommandError(f"要約コマンドの実行に失敗しました: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise SessionCommandError(
                f"要約コマンドが異常終了しました (exit {result.returncode}): {stderr}"
            )

        summary_text = (result.stdout or "").strip()
        if not summary_text:
            raise SessionCommandError("要約コマンドが空の出力を返しました。")

        timestamp = current_timestamp()
        block = f"{timestamp}\n{summary_text}"
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
        default=None,
        help="知識ベースディレクトリ (既定: 設定値または context/summaries)",
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
                    print("要約を conversation_log.md に追記しました。")
                    print(block)
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
            raise SessionCommandError(
                "AI_API_KEY が設定されていません。Codex コマンドの認証に必要です。"
            )

        config = load_config()
        session_cfg = config.get("session_manager", {})

        knowledge_dir_value = (
            args.knowledge_dir
            or session_cfg.get("knowledge_dir")
            or str(DEFAULT_KNOWLEDGE_DIR)
        )
        knowledge_dir = Path(knowledge_dir_value).expanduser().resolve()

        auto_preload_cfg = session_cfg.get("auto_preload")
        auto_preload = True if auto_preload_cfg is None else bool(auto_preload_cfg)

        preload_limit_cfg = session_cfg.get("preload_limit")
        if preload_limit_cfg is None:
            preload_limit: Optional[int] = None
        else:
            try:
                preload_limit = int(preload_limit_cfg)
            except (TypeError, ValueError) as exc:
                raise SessionCommandError("session_manager.preload_limit は整数で指定してください。") from exc
        summary_command_cfg = session_cfg.get("summary_command")
        if isinstance(summary_command_cfg, str):
            summary_command_value: Optional[Sequence[str]] = [summary_command_cfg]
        else:
            summary_command_value = summary_command_cfg

        summary_env_cfg = session_cfg.get("summary_env")
        summary_env: Optional[Dict[str, str]]
        if isinstance(summary_env_cfg, dict):
            summary_env = {str(key): str(value) for key, value in summary_env_cfg.items()}
        else:
            summary_env = None

        manager = SessionManager(
            knowledge_dir,
            auto_preload=auto_preload,
            preload_limit=preload_limit,
            summary_command=summary_command_value,
            summary_env=summary_env,
        )
        return _interactive_loop(manager)
    except SessionCommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - 想定外の例外
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
