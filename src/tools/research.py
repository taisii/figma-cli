"""研究支援ツール: 純粋ツールとしての入出力ユーティリティ群。"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

from src import convert


# 例外階層 -----------------------------------------------------------------


class ResearchError(Exception):
    """研究支援ツール全体の基底例外。"""


class ValidationError(ResearchError):
    """引数や入力値が仕様に反する場合の例外。"""


class NotFoundError(ResearchError):
    """対象リソースが存在しない場合の例外。"""


class IOError(ResearchError):  # noqa: A003 - 仕様上の名称に合わせる
    """ファイル入出力に起因する例外。"""


class ConflictError(ResearchError):
    """重複などの競合が発生した場合の例外。"""


class ConvertError(ResearchError):
    """変換処理に失敗した場合の例外。"""


# パス解決 -----------------------------------------------------------------


@dataclass(frozen=True)
class RepoPaths:
    base_dir: Path
    context_dir: Path
    papers_dir: Path
    summaries_dir: Path
    papers_index_path: Path
    summaries_index_path: Path


def _resolve_paths(base_dir: str | os.PathLike[str] | Path) -> RepoPaths:
    base = Path(base_dir).expanduser().resolve()
    context = base / "context"
    papers = context / "papers"
    summaries = context / "summaries" / "papers"
    papers_index = papers / "index.yaml"
    summaries_index = summaries / "index.json"
    return RepoPaths(
        base_dir=base,
        context_dir=context,
        papers_dir=papers,
        summaries_dir=summaries,
        papers_index_path=papers_index,
        summaries_index_path=summaries_index,
    )


# 共通ユーティリティ ---------------------------------------------------------


_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_slug(slug: str) -> None:
    if not _SLUG_PATTERN.match(slug):
        raise ValidationError("slug must be lowercase alphanumeric with hyphen")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as handle:
        handle.write(content)
        tmp_path = Path(handle.name)
    os.replace(tmp_path, path)


def _atomic_write_yaml(path: Path, payload: Any) -> None:
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    _atomic_write_text(path, text)


def _atomic_write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _atomic_write_text(path, text)


def _rel_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _split_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise yaml.YAMLError("invalid front matter")
    header_text = parts[0][4:]  # skip initial '---\n'
    body = parts[1]
    meta = yaml.safe_load(header_text)
    if meta is None:
        meta = {}
    elif not isinstance(meta, dict):
        raise yaml.YAMLError("front matter must be a mapping")
    return meta, body


def _compose_document(meta: Dict[str, Any], body: str) -> str:
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    body = body.lstrip("\n")
    if body and not body.endswith("\n"):
        body = body + "\n"
    return f"---\n{fm}\n---\n\n{body}" if fm else body


def _infer_title(markdown_body: str, fallback: str) -> str:
    for line in markdown_body.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip() or fallback
    return fallback


def _load_papers_index(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "papers": []}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise IOError(f"failed to parse papers index: {path}") from exc
    if not data:
        return {"version": 1, "papers": []}
    if isinstance(data, list):
        return {"version": 1, "papers": data}
    return {"version": data.get("version", 1), "papers": data.get("papers", [])}


def _upsert_papers_index(path: Path, entry: Dict[str, Any]) -> None:
    data = _load_papers_index(path)
    papers = [item for item in data["papers"] if item.get("slug") != entry.get("slug")]
    papers.append(entry)
    papers.sort(key=lambda item: item.get("slug", ""))
    payload = {"version": 1, "papers": papers}
    _atomic_write_yaml(path, payload)


def _find_paper_entry(path: Path, slug: str) -> Optional[Dict[str, Any]]:
    data = _load_papers_index(path)
    for item in data["papers"]:
        if item.get("slug") == slug:
            return item
    return None


def _load_summary_index(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "summaries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IOError(f"failed to parse summary index: {path}") from exc
    if not data:
        return {"version": 1, "summaries": []}
    return {"version": data.get("version", 1), "summaries": data.get("summaries", [])}


def _update_summary_index(path: Path, entry: Dict[str, Any]) -> None:
    data = _load_summary_index(path)
    summaries = [item for item in data["summaries"] if item.get("slug") != entry.get("slug")]
    summaries.append(entry)
    summaries.sort(key=lambda item: item.get("slug", ""))
    payload = {"version": 1, "summaries": summaries}
    _atomic_write_json(path, payload)


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise NotFoundError(f"file not found: {path}") from exc
    except OSError as exc:
        raise IOError(f"failed to read file: {path}") from exc


# チャンク化 -----------------------------------------------------------------


def chunk_markdown_for_llm(
    markdown_path: str | os.PathLike[str] | Path,
    out_dir: str | os.PathLike[str] | Path,
    *,
    strategy: str = "heading",
    max_chars: int = 4000,
    overlap: int = 200,
) -> Dict[str, Any]:
    """Markdown をチャンク分割して `chunks/` を生成する。"""

    path = Path(markdown_path)
    text = _read_file(path)
    meta, body = _split_front_matter(text)
    del meta  # front matter はチャンク内容から除外
    if strategy not in {"heading", "fixed"}:
        raise ValidationError(f"unsupported chunk strategy: {strategy}")

    if strategy == "fixed":
        chunk_texts = _chunk_fixed(body, max_chars=max_chars, overlap=overlap)
    else:
        chunk_texts = _chunk_by_heading(body, max_chars=max_chars, overlap=overlap)

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks: List[Dict[str, Any]] = []
    for index, chunk_text in enumerate(chunk_texts, start=1):
        chunk_id = f"{index:04d}"
        chunk_path = output_dir / f"{chunk_id}.md"
        chunk_path.write_text(chunk_text.strip() + "\n", encoding="utf-8")
        chunks.append({"id": chunk_id, "path": str(chunk_path), "char_count": len(chunk_text)})

    index_payload = {
        "version": 1,
        "strategy": strategy,
        "max_chars": max_chars,
        "overlap": overlap,
        "chunks": chunks,
    }
    index_path = output_dir / "index.json"
    _atomic_write_json(index_path, index_payload)

    return {"chunks": chunks, "index_path": str(index_path)}


def _chunk_fixed(text: str, *, max_chars: int, overlap: int) -> List[str]:
    if max_chars <= 0:
        raise ValidationError("max_chars must be positive")
    step = max(1, max_chars - max(0, overlap))
    chunks: List[str] = []
    pointer = 0
    while pointer < len(text):
        chunk = text[pointer : pointer + max_chars]
        if not chunk:
            break
        chunks.append(chunk)
        pointer += step
    return chunks or [text]


def _chunk_by_heading(text: str, *, max_chars: int, overlap: int) -> List[str]:
    sections = _split_sections(text)
    if not sections:
        return _chunk_fixed(text, max_chars=max_chars, overlap=overlap)

    chunks: List[str] = []
    current = ""
    for section in sections:
        if not current:
            current = section
            continue
        candidate = current + ("\n" if not current.endswith("\n") else "") + section
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            tail = current[-max(0, overlap) :] if overlap > 0 else ""
            current = (tail + section).lstrip("\n")
    if current:
        chunks.append(current)

    if not chunks:
        return _chunk_fixed(text, max_chars=max_chars, overlap=overlap)
    return chunks


def _split_sections(text: str) -> List[str]:
    sections: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if current:
                sections.append("\n".join(current).strip())
                current = []
            current.append(line)
        else:
            if not current:
                current.append(line)
            else:
                current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [section for section in sections if section.strip()]


# 主要 API -------------------------------------------------------------------


def convert_pdf_to_markdown(
    pdf_path: str | os.PathLike[str] | Path,
    out_dir: str | os.PathLike[str] | Path,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return convert.convert_pdf_to_markdown(pdf_path, out_dir, options=options)


def ingest_pdf(
    slug: str,
    pdf_path: str | os.PathLike[str] | Path,
    base_dir: str | os.PathLike[str] | Path,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _validate_slug(slug)
    paths = _resolve_paths(base_dir)
    paper_dir = paths.papers_dir / slug
    paper_dir.mkdir(parents=True, exist_ok=True)

    try:
        convert_result = convert.convert_pdf_to_markdown(pdf_path, paper_dir, options=options)
    except convert.ConvertError as exc:
        raise ConvertError(str(exc)) from exc

    main_md_path = Path(convert_result["main_md_path"])
    markdown_raw = _read_file(main_md_path)
    body_meta, body = _split_front_matter(markdown_raw)
    del body_meta

    title = _infer_title(body, slug.replace("-", " ").title())
    now = _now()
    pages = len(convert_result["page_map"]) if convert_result.get("page_map") else 0
    hash_info = {
        "pdf_sha256": convert_result["pdf_sha256"],
        "docling_opts": convert_result["docling_opts_sha256"],
    }
    front_matter = {
        "title": title,
        "slug": slug,
        "pages": pages,
        "hash": hash_info,
        "updated_at": now,
    }
    document_text = _compose_document(front_matter, body)
    _atomic_write_text(main_md_path, document_text)

    # 入力 PDF を保存
    pdf_target = paper_dir / "source.pdf"
    shutil.copy2(pdf_path, pdf_target)

    chunks_dir = paper_dir / "chunks"
    chunk_result = chunk_markdown_for_llm(main_md_path, chunks_dir)

    chunk_index_path = Path(chunk_result["index_path"])
    entry = {
        "slug": slug,
        "title": title,
        "md_path": _rel_path(main_md_path, paths.base_dir),
        "assets_dir": _rel_path(Path(convert_result["assets_dir"]), paths.base_dir),
        "tables_dir": _rel_path(Path(convert_result["tables_dir"]), paths.base_dir),
        "chunk_index_path": _rel_path(chunk_index_path, paths.base_dir),
        "chunk_count": len(chunk_result["chunks"]),
        "pages": pages,
        "hash": hash_info,
        "updated_at": now,
        "source_pdf": _rel_path(pdf_target, paths.base_dir),
    }
    _upsert_papers_index(paths.papers_index_path, entry)

    return {
        "slug": slug,
        "main_md_path": str(main_md_path),
        "chunk_index_path": str(chunk_index_path),
        "chunks": chunk_result["chunks"],
        "page_map": convert_result["page_map"],
        "hash": hash_info,
    }


def list_papers(base_dir: str | os.PathLike[str] | Path) -> List[Dict[str, Any]]:
    paths = _resolve_paths(base_dir)
    data = _load_papers_index(paths.papers_index_path)
    entries: List[Dict[str, Any]] = []
    for raw in data["papers"]:
        normalized = dict(raw)
        normalized["md_path"] = str(paths.base_dir / normalized.get("md_path", ""))
        normalized["assets_dir"] = str(paths.base_dir / normalized.get("assets_dir", ""))
        normalized["tables_dir"] = str(paths.base_dir / normalized.get("tables_dir", ""))
        if "summary_path" in normalized:
            normalized["summary_path"] = str(paths.base_dir / normalized["summary_path"])
        entries.append(normalized)
    return entries


def load_paper(
    slug: str,
    base_dir: str | os.PathLike[str] | Path,
    *,
    max_chars: Optional[int] = None,
) -> Dict[str, Any]:
    paths = _resolve_paths(base_dir)
    paper_path = paths.papers_dir / slug / "main.md"
    text = _read_file(paper_path)
    meta, body = _split_front_matter(text)

    content = body
    truncated = False
    if max_chars is not None and max_chars >= 0 and len(body) > max_chars:
        content = body[:max_chars]
        truncated = True

    return {
        "slug": slug,
        "content": content,
        "truncated": truncated,
        "meta": meta,
        "path": str(paper_path),
    }


def save_summary(
    slug: str,
    content: str,
    base_dir: str | os.PathLike[str] | Path,
    *,
    tags: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    _validate_slug(slug)
    paths = _resolve_paths(base_dir)

    entry = _find_paper_entry(paths.papers_index_path, slug)
    if entry is None:
        raise NotFoundError(f"paper not indexed: {slug}")

    paper_path = paths.base_dir / entry["md_path"]
    text = _read_file(paper_path)
    meta, _ = _split_front_matter(text)

    chunk_index_path = paths.base_dir / entry["chunk_index_path"]
    if not chunk_index_path.exists():
        raise NotFoundError(f"chunk index not found: {chunk_index_path}")
    chunk_index = json.loads(chunk_index_path.read_text(encoding="utf-8"))
    chunk_refs = [item["id"] for item in chunk_index.get("chunks", [])]

    tags_list = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    updated_at = _now()
    summary_dir = paths.summaries_dir
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / f"{slug}.md"

    summary_meta = {
        "slug": slug,
        "tags": tags_list,
        "updated_at": updated_at,
    }
    summary_body = (content or "").rstrip() + "\n"
    summary_text = _compose_document(summary_meta, summary_body)
    _atomic_write_text(summary_path, summary_text)

    source_hash = meta.get("hash", {}).get("pdf_sha256", "")
    summary_entry = {
        "slug": slug,
        "path": _rel_path(summary_path, paths.base_dir),
        "title": meta.get("title") or slug,
        "tags": tags_list,
        "source_hash": source_hash,
        "chunk_refs": chunk_refs,
        "updated_at": updated_at,
    }
    _update_summary_index(paths.summaries_index_path, summary_entry)

    entry_updated = dict(entry)
    entry_updated["summary_path"] = summary_entry["path"]
    entry_updated["summary_updated_at"] = updated_at
    _upsert_papers_index(paths.papers_index_path, entry_updated)

    return {
        "summary_path": str(summary_path),
        "chunk_refs": chunk_refs,
        "updated_at": updated_at,
    }


__all__ = [
    "convert_pdf_to_markdown",
    "ingest_pdf",
    "chunk_markdown_for_llm",
    "list_papers",
    "load_paper",
    "save_summary",
    "ResearchError",
    "ValidationError",
    "NotFoundError",
    "IOError",
    "ConflictError",
    "ConvertError",
]
