"""研究支援ツール関数（API非依存）。

Codex CLI などの会話エンジンから“ツール”として直接呼ばれることを想定。
ここでは LLM/API を一切呼び出さず、ファイル入出力とインデックス更新のみを行う。

主な提供関数:
- list_papers(config: dict | None = None) -> list[dict]
- load_paper(slug: str, max_chars: int | None = None, config: dict | None = None) -> dict
- save_summary(slug: str, content: str, tags: list[str] | None = None, config: dict | None = None) -> dict

設定は `config.yaml` の以下キーを利用（無い場合は既定値）。
- document_ingest.raw_dir: str                    (既定: "data/raw/papers")
- document_ingest.processed_dir: str              (既定: "context/papers")
- document_ingest.summaries_dir: str              (既定: "context/summaries/papers")
- document_ingest.summary_index_path: str         (既定: "context/summaries/papers/index.json")
- document_ingest.index_path: str                 (既定: "context/papers/index.yaml")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import json
import os
import re
import yaml


# --------------------------------------------------------------------
# 設定/パス解決


@dataclass(frozen=True)
class Paths:
    raw_dir: Path
    processed_dir: Path
    summaries_dir: Path
    summary_index_path: Path
    index_path: Path


def load_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as h:
            return yaml.safe_load(h) or {}
    except FileNotFoundError:
        return {}


def _paths(config: Optional[dict] = None) -> Paths:
    cfg = dict(config or {})
    ingest = cfg.get("document_ingest") or cfg.get("paths") or {}
    raw_dir = Path(ingest.get("raw_dir", "data/raw/papers"))
    processed_dir = Path(ingest.get("processed_dir", "context/papers"))
    summaries_dir = Path(ingest.get("summaries_dir", "context/summaries/papers"))
    summary_index_path = Path(ingest.get("summary_index_path", "context/summaries/papers/index.json"))
    index_path = Path(ingest.get("index_path", "context/papers/index.yaml"))
    return Paths(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        summaries_dir=summaries_dir,
        summary_index_path=summary_index_path,
        index_path=index_path,
    )


def _ensure_dirs(paths: Paths) -> None:
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    paths.summaries_dir.mkdir(parents=True, exist_ok=True)
    paths.summary_index_path.parent.mkdir(parents=True, exist_ok=True)
    paths.index_path.parent.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------
# ユーティリティ


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml(path: Path) -> dict:
    """緩やかな YAML 読み込み（失敗時は空辞書）。一覧表示などの読み取り用途で使用。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError:
        return {}


def _read_yaml_strict(path: Path) -> dict:
    """厳密な YAML 読み込み。構文エラー時は例外を送出し、上書きを防ぐ。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    # 構文エラーは呼び出し元へ伝播させる
    


def _write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as h:
        yaml.safe_dump(data, h, allow_unicode=True, sort_keys=False)


def _relativize(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _frontmatter_from_markdown(md_path: Path) -> dict:
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---\n"):
        return {}
    try:
        _, fm, _ = text.split("---\n", 2)
    except ValueError:
        return {}
    try:
        return yaml.safe_load(fm) or {}
    except yaml.YAMLError:
        return {}


def _slugify(value: str) -> str:
    v = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return v or "document"


def _sync_summary_alias(summary_path: Path, alias_path: Path) -> Path:
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    if alias_path.exists() or alias_path.is_symlink():
        try:
            alias_path.unlink()
        except OSError:
            pass
    try:
        rel = os.path.relpath(summary_path, alias_path.parent)
        alias_path.symlink_to(rel)
    except (OSError, NotImplementedError, ValueError):
        # シンボリックリンク不可の場合はコピー
        import shutil as _shutil

        _shutil.copy2(summary_path, alias_path)
    return alias_path


# --------------------------------------------------------------------
# 公開ツール関数


def _normalize_authors(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def list_papers(config: Optional[dict] = None) -> List[dict]:
    """登録された論文の概要を列挙する。

    - `context/papers/<slug>/paper.md` を持つディレクトリを対象
    - `metadata.yaml` があれば優先、無ければ Markdown の frontmatter を補完
    - 返却は機械可読な辞書のリスト
    """

    p = _paths(config)
    _ensure_dirs(p)

    entries: List[dict] = []
    for slug_dir in sorted([d for d in p.processed_dir.iterdir() if d.is_dir()]):
        slug = slug_dir.name
        paper_path = slug_dir / "paper.md"
        if not paper_path.exists():
            continue
        meta_path = slug_dir / "metadata.yaml"
        meta = _read_yaml(meta_path)
        # frontmatter は常に読み、フィールド単位でフォールバック（回帰防止）
        fm = _frontmatter_from_markdown(paper_path)

        title = meta.get("title") or fm.get("title") or slug
        authors_val = meta.get("authors") or fm.get("authors")
        authors = _normalize_authors(authors_val)
        year = meta.get("year") or fm.get("year")

        summary_path = slug_dir / "summary.md"
        alias_path = p.summaries_dir / f"{slug}.md"
        entries.append(
            {
                "id": slug,
                "title": title,
                "authors": authors,
                "year": year,
                "paper_path": _relativize(paper_path, p.processed_dir.parent),
                "summary_path": _relativize(summary_path, p.processed_dir.parent)
                if summary_path.exists()
                else None,
                "summary_alias_path": _relativize(alias_path, p.summaries_dir.parent)
                if alias_path.exists()
                else None,
            }
        )

    return entries


def load_paper(
    slug: str,
    max_chars: Optional[int] = None,
    config: Optional[dict] = None,
) -> dict:
    """`paper.md` を読み出し、必要に応じて文字数を制限して返す。

    戻り値: { slug, content, truncated, paper_path }
    """

    p = _paths(config)
    paper_path = p.processed_dir / slug / "paper.md"
    if not paper_path.exists():
        raise FileNotFoundError(f"paper.md not found for slug: {slug}")

    text = paper_path.read_text(encoding="utf-8")
    truncated = False
    if max_chars is not None and max_chars >= 0 and len(text) > max_chars:
        text = text[: max_chars]
        truncated = True

    return {
        "slug": slug,
        "content": text,
        "truncated": truncated,
        "paper_path": str(paper_path),
    }


def save_summary(
    slug: str,
    content: str,
    *,
    tags: Optional[List[str]] = None,
    config: Optional[dict] = None,
) -> dict:
    """`summary.md` の保存と索引更新・エイリアス同期を行う純粋ツール。

    - LLM/API を呼ばない。与えられた `content` を保存してメタ情報を更新する。
    - 更新対象
      - context/papers/<slug>/summary.md（上書き）
      - context/summaries/papers/<slug>.md（シンボリックリンク or コピー）
      - context/papers/index.yaml（該当エントリを upsert）
      - context/summaries/papers/index.json（該当エントリを upsert）
    戻り値: { summary_path, summary_alias_path }
    """

    p = _paths(config)
    _ensure_dirs(p)

    target_dir = p.processed_dir / slug
    paper_path = target_dir / "paper.md"
    if not target_dir.exists() or not paper_path.exists():
        raise FileNotFoundError(
            f"ingested paper not found for slug '{slug}'. expected: {paper_path}"
        )

    # metadata.yaml の upsert
    meta_path = target_dir / "metadata.yaml"
    # 厳密読み込み: 構文エラー時は保存を中止して例外を伝播
    meta = _read_yaml_strict(meta_path)
    meta.setdefault("id", slug)

    # 既存タイトルが無い場合は frontmatter から補完
    if not meta.get("title") and paper_path.exists():
        fm = _frontmatter_from_markdown(paper_path)
        if fm.get("title"):
            meta["title"] = fm.get("title")

    # ingested_at が無い古いエントリに対しては今を設定
    meta.setdefault("ingested_at", _now())
    if tags:
        existing = list(meta.get("tags", []) or [])
        merged = list(dict.fromkeys([*existing, *tags]))
        meta["tags"] = merged

    meta["summary_generated"] = True
    meta["summary_updated_at"] = _now()
    # summary はメタデータ更新後に書き込む（前段で例外が起きた場合に破壊を避ける）
    summary_path = target_dir / "summary.md"
    alias_path = p.summaries_dir / f"{slug}.md"
    meta["summary_path"] = _relativize(summary_path, p.processed_dir.parent)
    meta["summary_alias_path"] = _relativize(alias_path, p.summaries_dir.parent)

    _write_yaml(meta_path, meta)

    # 実体と別名の同期（メタデータが確定してから実ファイルを生成）
    summary_path.write_text((content or "").rstrip() + "\n", encoding="utf-8")
    _sync_summary_alias(summary_path, alias_path)

    # index.yaml の upsert
    _upsert_index_yaml(p.index_path, meta)

    # summaries の簡易インデックスを更新
    _upsert_summary_index_json(p.summary_index_path, meta)

    return {
        "summary_path": str(summary_path),
        "summary_alias_path": str(alias_path),
    }


# --------------------------------------------------------------------
# インデックス更新実装


def _upsert_index_yaml(index_path: Path, entry: dict) -> None:
    if index_path.exists():
        try:
            data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or []
        except yaml.YAMLError:
            data = []
    else:
        data = []

    data = [item for item in data if item.get("id") != entry.get("id")]
    data.append(entry)
    # 可能なら時系列順
    data.sort(key=lambda x: x.get("ingested_at", ""))

    with index_path.open("w", encoding="utf-8") as h:
        yaml.safe_dump(data, h, allow_unicode=True, sort_keys=False)


def _upsert_summary_index_json(summary_index_path: Path, meta: dict) -> None:
    if summary_index_path.exists():
        try:
            items = json.loads(summary_index_path.read_text(encoding="utf-8")) or []
        except (json.JSONDecodeError, OSError):
            items = []
    else:
        items = []

    items = [it for it in items if it.get("id") != meta.get("id")]

    payload = {
        "id": meta.get("id"),
        "title": meta.get("title") or meta.get("id"),
        "summary_path": meta.get("summary_path"),
        "summary_alias_path": meta.get("summary_alias_path"),
        "source_type": meta.get("source_type") or "",
        "tags": meta.get("tags", []),
        "updated_at": meta.get("summary_updated_at") or meta.get("ingested_at"),
    }
    items.append(payload)
    items.sort(key=lambda x: x.get("updated_at", ""))

    summary_index_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "load_config",
    "list_papers",
    "load_paper",
    "save_summary",
    "convert_pdf_tool",
]


def convert_pdf_tool(
    pdf_path: str,
    output_dir: Optional[str] = None,
    *,
    force: bool = False,
) -> dict:
    """PDF を Markdown に変換するツール関数（Docling 使用、LLM 非依存）。

    引数:
    - pdf_path: 入力 PDF のパス
    - output_dir: 出力ディレクトリ（既定: data/generated）
    - force: 既存 Markdown がある場合も上書きするか

    戻り値: { markdown_path }
    例外: 入力が無い/拡張子不正/変換失敗などで例外を送出
    """

    from src import convert as _convert

    pdf = Path(pdf_path).expanduser().resolve()
    out_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else Path("data/generated").resolve()
    )
    md_path = _convert.convert_pdf(pdf, out_dir, force=force)
    return {"markdown_path": str(md_path)}
