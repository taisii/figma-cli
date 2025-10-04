"""Model Context Protocol (MCP) サーバーのラッパー実装。

`src.tools.research` が提供する純粋ツール関数を MCP サーバーとして公開する。

このモジュールは `mcp` パッケージに依存する。実行環境に `mcp` がインストール
されていない場合は ImportError を送出するため、利用前に明示的にインストールすること。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from src.tools import research

try:  # pragma: no cover - import 時にのみ評価
    from mcp.server import Server
    from mcp.server.errors import ToolNotFoundError
    from mcp.server.models import CallToolRequest, TextContent, Tool, ToolResponse
    from mcp.server.stdio import stdio_server
except ImportError as exc:  # pragma: no cover - 実行時エラーに置き換える
    Server = None  # type: ignore[assignment]
    Tool = None  # type: ignore[assignment]
    ToolResponse = None  # type: ignore[assignment]
    CallToolRequest = None  # type: ignore[assignment]
    TextContent = None  # type: ignore[assignment]
    ToolNotFoundError = RuntimeError  # type: ignore[assignment]
    stdio_server = None  # type: ignore[assignment]
    _IMPORT_ERROR: Exception | None = exc
else:
    _IMPORT_ERROR = None


def _require_mcp() -> None:
    """`mcp` パッケージが利用可能か検証し、無い場合は ImportError を送出する。"""

    if Server is None or _IMPORT_ERROR is not None:  # pragma: no cover - 実行時検証
        raise ImportError(
            "mcp パッケージが見つかりません。`pip install modelcontextprotocol` 等で "
            "インストールしてください"
        ) from _IMPORT_ERROR


def _tool_list() -> list[Tool]:
    """MCP ツール定義を返す。"""

    _require_mcp()

    return [
        Tool(
            name="list_papers",
            description="登録済みの論文概要を列挙します",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="load_paper",
            description="指定した slug の paper.md を返します",
            input_schema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "max_chars": {"type": ["integer", "null"], "minimum": 0},
                },
                "required": ["slug"],
            },
        ),
        Tool(
            name="save_summary",
            description="paper.md の要約と索引を更新します",
            input_schema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                    },
                },
                "required": ["slug", "content"],
            },
        ),
        Tool(
            name="convert_pdf_tool",
            description="Docling を利用して PDF を Markdown に変換します",
            input_schema={
                "type": "object",
                "properties": {
                    "pdf_path": {"type": "string"},
                    "output_dir": {
                        "type": ["string", "null"],
                    },
                    "force": {"type": "boolean", "default": False},
                },
                "required": ["pdf_path"],
            },
        ),
    ]


def _dispatch_tool(name: str, arguments: dict[str, Any] | None) -> Dict[str, Any]:
    """`src.tools.research` の関数にディスパッチする。"""

    args = dict(arguments or {})
    if name == "list_papers":
        return {"items": research.list_papers()}
    if name == "load_paper":
        try:
            slug = args["slug"]
        except KeyError as exc:  # pragma: no cover - 引数チェック
            raise ValueError("'slug' は必須です") from exc
        return research.load_paper(slug=slug, max_chars=args.get("max_chars"))
    if name == "save_summary":
        try:
            slug = args["slug"]
            content = args["content"]
        except KeyError as exc:  # pragma: no cover - 引数チェック
            raise ValueError("'slug' と 'content' は必須です") from exc
        return research.save_summary(slug=slug, content=content, tags=args.get("tags"))
    if name == "convert_pdf_tool":
        try:
            pdf_path = args["pdf_path"]
        except KeyError as exc:  # pragma: no cover - 引数チェック
            raise ValueError("'pdf_path' は必須です") from exc
        return research.convert_pdf_tool(
            pdf_path=pdf_path,
            output_dir=args.get("output_dir"),
            force=bool(args.get("force", False)),
        )
    raise ToolNotFoundError(name)


def create_server(name: str = "figma-research") -> Server:
    """MCP サーバーインスタンスを生成する。"""

    _require_mcp()
    server = Server(name)

    @server.list_tools()
    async def _list_tools() -> Iterable[Tool]:
        return _tool_list()

    @server.call_tool()
    async def _call_tool(request: CallToolRequest) -> ToolResponse:
        payload = _dispatch_tool(request.name, request.arguments)
        return ToolResponse(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(payload, ensure_ascii=False, indent=2),
                )
            ]
        )

    return server


def run_stdio_server(name: str = "figma-research") -> None:
    """標準入出力ベースの MCP サーバーを起動する。"""

    _require_mcp()
    server = create_server(name)
    stdio_server.run(server)


__all__ = ["create_server", "run_stdio_server"]


if __name__ == "__main__":  # pragma: no cover - CLI 起動用
    run_stdio_server()
