import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml
from pypdf import PdfReader

try:  # pragma: no cover - optional dependency used for richer TeX conversion
    from pylatexenc.latex2text import LatexNodes2Text
except ImportError:  # pragma: no cover
    LatexNodes2Text = None

LATEX_TO_TEXT = LatexNodes2Text() if LatexNodes2Text is not None else None

class DocumentIngestionError(Exception):
    """Raised when an asset cannot be processed."""


@dataclass
class IngestionResult:
    slug: str
    paper_path: Path
    summary_path: Path
    summary_alias_path: Path
    metadata_path: Path
    source_path: Path
    message: str


@dataclass
class SummaryGenerationResult:
    slug: str
    summary_path: Path
    summary_alias_path: Path
    regenerated: bool


class DocumentIngestor:
    """Ingest PDF or TeX sources into the knowledge base."""

    def __init__(self, config: Dict):
        self.config = config
        ingestion_cfg = config.get("document_ingest") or config.get("pdf_ingest", {})
        self.raw_dir = Path(ingestion_cfg.get("raw_dir", "data/raw/papers"))
        self.processed_dir = Path(ingestion_cfg.get("processed_dir", "context/papers"))
        self.summaries_dir = Path(ingestion_cfg.get("summaries_dir", "context/summaries"))
        self.summary_index_path = Path(
            ingestion_cfg.get("summary_index_path", "context/summaries/index.json")
        )
        command_value = ingestion_cfg.get("summary_command", ["codex", "prompt", "summary"])
        if isinstance(command_value, str):
            self.summary_command = [command_value]
        else:
            self.summary_command = list(command_value)
        self.index_path = Path(ingestion_cfg.get("index_path", "context/index.yaml"))

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.summary_index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API

    def ingest_pdf(
        self,
        pdf_path: Path,
        *,
        force: bool = False,
        copy_to_raw: bool = True,
        slug: Optional[str] = None,
    ) -> IngestionResult:
        pdf_path = pdf_path.expanduser().resolve()
        if not pdf_path.exists():
            raise DocumentIngestionError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise DocumentIngestionError("Only .pdf files are supported.")

        raw_pdf_path = self._prepare_raw_pdf(pdf_path, copy_to_raw)

        metadata = self._extract_pdf_metadata(raw_pdf_path)
        slug_value = slug or self._build_slug(metadata, raw_pdf_path.stem)
        target_dir = self.processed_dir / slug_value

        if target_dir.exists():
            if self._is_ingestion_complete(target_dir):
                if not force:
                    return self._build_existing_result(slug_value, raw_pdf_path, target_dir)
                self._remove_summary_alias(slug_value)
                shutil.rmtree(target_dir)
            else:
                self._remove_summary_alias(slug_value)
                shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        markdown = self._convert_pdf_to_markdown(raw_pdf_path)
        paper_body = markdown.strip()

        paper_path = target_dir / "paper.md"
        paper_path.write_text(self._compose_markdown(metadata, paper_body), encoding="utf-8")

        metadata_payload = self._build_metadata_payload(
            slug_value,
            metadata,
            raw_pdf_path,
            paper_path,
            source_type="pdf",
            extra={}
        )
        metadata_path = target_dir / "metadata.yaml"
        with metadata_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(metadata_payload, handle, allow_unicode=True, sort_keys=False)

        self._update_index(metadata_payload)

        message = f"Ingested '{metadata_payload['title']}' into {target_dir}"
        return IngestionResult(
            slug=slug_value,
            paper_path=paper_path,
            summary_path=target_dir / "summary.md",
            summary_alias_path=self.summaries_dir / f"{slug_value}.md",
            metadata_path=metadata_path,
            source_path=raw_pdf_path,
            message=message,
        )

    def ingest_tex_folder(
        self,
        tex_dir: Path,
        *,
        root_file: Optional[str] = None,
        force: bool = False,
        copy_to_raw: bool = True,
        slug: Optional[str] = None,
    ) -> IngestionResult:
        tex_dir = tex_dir.expanduser().resolve()
        if not tex_dir.exists() or not tex_dir.is_dir():
            raise DocumentIngestionError(f"TeX directory not found: {tex_dir}")

        root_tex = self._resolve_root_tex(tex_dir, root_file)
        expanded_tex = self._expand_tex_to_single_file(root_tex)
        metadata = self._extract_tex_metadata(expanded_tex)
        slug_value = slug or self._build_slug(metadata, root_tex.stem)

        raw_source_path = self._prepare_raw_tex(tex_dir, slug_value, copy_to_raw)

        target_dir = self.processed_dir / slug_value
        if target_dir.exists():
            if self._is_ingestion_complete(target_dir):
                if not force:
                    return self._build_existing_result(slug_value, raw_source_path, target_dir)
                self._remove_summary_alias(slug_value)
                shutil.rmtree(target_dir)
            else:
                self._remove_summary_alias(slug_value)
                shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        markdown = self._convert_tex_to_markdown(expanded_tex)
        macros = self._extract_macro_definitions(expanded_tex)
        chunks = self._split_markdown_chunks(markdown)

        paper_path = target_dir / "paper.md"
        paper_path.write_text(self._compose_markdown(metadata, markdown), encoding="utf-8")

        macros_path = self._write_macros(macros, target_dir)
        chunks_index = self._write_chunks(chunks, target_dir)

        metadata_payload = self._build_metadata_payload(
            slug_value,
            metadata,
            raw_source_path,
            paper_path,
            source_type="tex",
            extra={
                "macros_path": self._relativize(macros_path, self.processed_dir.parent),
                "chunks_index": self._relativize(chunks_index, self.processed_dir.parent),
            },
        )

        metadata_payload["root_file"] = self._relativize(root_tex, tex_dir.parent)

        metadata_path = target_dir / "metadata.yaml"
        with metadata_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(metadata_payload, handle, allow_unicode=True, sort_keys=False)

        self._update_index(metadata_payload)

        message = f"Ingested TeX project '{metadata_payload['title']}' into {target_dir}"
        return IngestionResult(
            slug=slug_value,
            paper_path=paper_path,
            summary_path=target_dir / "summary.md",
            summary_alias_path=self.summaries_dir / f"{slug_value}.md",
            metadata_path=metadata_path,
            source_path=raw_source_path,
            message=message,
        )

    def ingest_all_pending(self, *, force: bool = False) -> Sequence[IngestionResult]:
        pdf_files = sorted(self.raw_dir.glob("*.pdf"))
        tex_dirs = [p for p in self.raw_dir.iterdir() if p.is_dir() and any(p.glob("*.tex"))]

        results: List[IngestionResult] = []
        errors: List[str] = []

        for pdf_file in pdf_files:
            try:
                results.append(
                    self.ingest_pdf(
                        pdf_file,
                        force=force,
                        copy_to_raw=False,
                    )
                )
            except DocumentIngestionError as exc:
                errors.append(f"{pdf_file.name}: {exc}")

        for tex_dir in tex_dirs:
            try:
                results.append(
                    self.ingest_tex_folder(
                        tex_dir,
                        force=force,
                        copy_to_raw=False,
                    )
                )
            except DocumentIngestionError as exc:
                errors.append(f"{tex_dir.name}: {exc}")

        if errors:
            raise DocumentIngestionError("\n".join(errors))

        if not results:
            raise DocumentIngestionError("No PDFs or TeX projects found in the raw inbox.")

        return results

    # ------------------------------------------------------------------
    # PDF helpers

    def _prepare_raw_pdf(self, pdf_path: Path, copy_to_raw: bool) -> Path:
        if copy_to_raw:
            destination = (self.raw_dir / pdf_path.name).resolve()
            if pdf_path != destination:
                shutil.copy2(pdf_path, destination)
            return destination
        return pdf_path

    def _extract_pdf_metadata(self, pdf_path: Path) -> Dict:
        metadata: Dict[str, Optional[str]] = {
            "title": pdf_path.stem,
            "authors": [],
            "year": None,
            "doi": None,
        }
        try:
            reader = PdfReader(str(pdf_path))
            info = reader.metadata or {}
        except Exception:
            return metadata

        title = getattr(info, "title", None) or info.get("/Title")
        if title:
            metadata["title"] = title.strip()

        author_value = getattr(info, "author", None) or info.get("/Author")
        if author_value:
            metadata["authors"] = [part.strip() for part in re.split(r"[;,]", author_value) if part.strip()]

        creation_date = getattr(info, "creation_date", None) or info.get("/CreationDate")
        year = self._parse_pdf_year(creation_date)
        if year:
            metadata["year"] = year

        doi = info.get("/doi") or info.get("doi")
        if doi:
            metadata["doi"] = doi

        return metadata

    def _convert_pdf_to_markdown(self, pdf_path: Path) -> str:
        reader = PdfReader(str(pdf_path))
        parts: List[str] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            parts.append(f"## Page {idx}\n\n{text.strip()}\n")
        return "\n".join(parts).strip() or ""

    def _parse_pdf_year(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        match = re.search(r"(19|20)\d{2}", str(value))
        if match:
            return match.group(0)
        return None

    # ------------------------------------------------------------------
    # TeX helpers

    def _resolve_root_tex(self, tex_dir: Path, root_file: Optional[str]) -> Path:
        if root_file:
            candidate = (tex_dir / root_file).resolve()
            if candidate.exists():
                return candidate
            raise DocumentIngestionError(f"Specified root file not found: {root_file}")

        tex_files = list(tex_dir.rglob("*.tex"))
        if not tex_files:
            raise DocumentIngestionError("No .tex files found in the directory.")

        preferred = [tex_dir / "main.tex", tex_dir / f"{tex_dir.name}.tex"]
        for candidate in preferred:
            if candidate.exists():
                return candidate.resolve()

        if len(tex_files) == 1:
            return tex_files[0].resolve()

        # fallback: choose shortest path (likely top-level)
        tex_files.sort(key=lambda p: (len(p.parts), p.name))
        return tex_files[0].resolve()

    def _prepare_raw_tex(self, tex_dir: Path, slug: str, copy_to_raw: bool) -> Path:
        if not copy_to_raw:
            return tex_dir
        destination = (self.raw_dir / slug).resolve()
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(tex_dir, destination)
        return destination

    def _expand_tex_to_single_file(self, root_tex: Path) -> str:
        if shutil.which("latexpand"):
            with tempfile.NamedTemporaryFile("w", suffix=".tex", encoding="utf-8", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            try:
                with tmp_path.open("w", encoding="utf-8") as handle:
                    subprocess.run(
                        ["latexpand", "--keep-comments", str(root_tex)],
                        check=True,
                        stdout=handle,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                return tmp_path.read_text(encoding="utf-8")
            except subprocess.CalledProcessError as exc:
                raise DocumentIngestionError(f"latexpand failed: {exc.stderr}") from exc
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        return root_tex.read_text(encoding="utf-8")

    def _convert_tex_to_markdown(self, expanded_tex: str) -> str:
        if shutil.which("pandoc"):
            with tempfile.NamedTemporaryFile("w", suffix=".tex", encoding="utf-8", delete=False) as tex_file:
                tex_file.write(expanded_tex)
                tex_path = Path(tex_file.name)
            md_path = tex_path.with_suffix(".md")
            try:
                subprocess.run(
                    [
                        "pandoc",
                        "--from",
                        "latex",
                        "--to",
                        "gfm",
                        str(tex_path),
                        "--output",
                        str(md_path),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return md_path.read_text(encoding="utf-8")
            except subprocess.CalledProcessError as exc:
                raise DocumentIngestionError(f"pandoc failed: {exc.stderr}") from exc
            finally:
                if tex_path.exists():
                    tex_path.unlink()
                if md_path.exists():
                    md_path.unlink()
        return self._fallback_tex_to_markdown(expanded_tex)

    def _fallback_tex_to_markdown(self, expanded_tex: str) -> str:
        text = re.sub(r"%.*$", "", expanded_tex, flags=re.MULTILINE)
        text = text.replace("\r", "")

        heading_map = {
            "section": "#",
            "subsection": "##",
            "subsubsection": "###",
            "paragraph": "####",
        }

        for command, hashes in heading_map.items():
            pattern = rf"\\{command}\*?\{{([^}}]*)\}}"
            text = re.sub(
                pattern,
                lambda m: f"\n{hashes} {self._strip_latex(m.group(1))}\n\n",
                text,
            )

        text = re.sub(r"\\begin\{abstract\}", "\n## Abstract\n\n", text)
        text = re.sub(r"\\end\{abstract\}", "\n", text)
        text = re.sub(r"\\begin\{itemize\}|\\begin\{enumerate\}", "\n", text)
        text = re.sub(r"\\end\{itemize\}|\\end\{enumerate\}", "\n", text)
        text = re.sub(r"\\item", "\n- ", text)

        emphasis_replacements = {
            r"\\textbf\{([^}]*)\}": ("**", "**"),
            r"\\textit\{([^}]*)\}": ("*", "*"),
            r"\\emph\{([^}]*)\}": ("*", "*"),
        }
        for pattern, (prefix, suffix) in emphasis_replacements.items():
            text = re.sub(
                pattern,
                lambda m: f"{prefix}{self._strip_latex(m.group(1))}{suffix}",
                text,
            )

        text = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", "\n", text)

        strip_commands = [
            r"\\documentclass[^\n]*",
            r"\\maketitle",
            r"\\thispagestyle[^\n]*",
            r"\\pagestyle[^\n]*",
            r"\\tableofcontents",
            r"\\title[^\n]*",
            r"\\author[^\n]*",
            r"\\IEEEauthorblockN[^\n]*",
            r"\\IEEEauthorblockA[^\n]*",
            r"\\IEEEauthorrefmark[^\n]*",
            r"\\newcommand[^\n]*",
            r"\\renewcommand[^\n]*",
            r"\\usepackage[^\n]*",
            r"\\input[^\n]*",
            r"\\include[^\n]*",
            r"\\bibliography[^\n]*",
        ]
        for pattern in strip_commands:
            text = re.sub(pattern, "", text)

        replacements = {
            "\\qquad": " ",
            "\\quad": " ",
            "\\newline": "\n",
            "\\\\": "\n",
        }
        for needle, repl in replacements.items():
            text = text.replace(needle, repl)

        if LATEX_TO_TEXT is not None:
            text = LATEX_TO_TEXT.latex_to_text(text)
        else:
            text = text.replace("\\", "\n")
            text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^]]*\])?", "", text)
            text = text.replace("{", "").replace("}", "")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        cleaned_lines = [line.rstrip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in cleaned_lines if line.strip())
        return cleaned.strip()

    def _extract_tex_metadata(self, expanded_tex: str) -> Dict:
        metadata: Dict[str, Optional[str]] = {
            "title": None,
            "authors": [],
            "year": None,
            "doi": None,
        }
        title_value = self._extract_braced_value(expanded_tex, "title")
        if title_value is not None:
            metadata["title"] = self._strip_latex(title_value.strip()) or None

        author_value = self._extract_braced_value(expanded_tex, "author")
        if author_value is not None:
            block_value = self._extract_braced_value(author_value, "IEEEauthorblockN")
            if block_value is not None:
                raw_authors = re.split(r"\\and|,| and ", block_value)
            else:
                raw_authors = re.split(r"\\and|,| and ", author_value)
            cleaned_authors: List[str] = []
            for author in raw_authors:
                stripped = self._strip_latex(author.strip())
                if stripped:
                    cleaned_authors.append(stripped)
            metadata["authors"] = cleaned_authors
        date_value = self._extract_braced_value(expanded_tex, "date")
        if date_value is not None:
            metadata["year"] = self._strip_latex(date_value.strip()) or None
        doi_value = self._extract_braced_value(expanded_tex, "doi")
        if doi_value is not None:
            metadata["doi"] = self._strip_latex(doi_value.strip()) or None
        if not metadata["title"]:
            metadata["title"] = "Untitled TeX Document"
        return metadata

    def _extract_macro_definitions(self, expanded_tex: str) -> List[str]:
        pattern = re.compile(r"^(\\(?:re)?newcommand.*)$", flags=re.MULTILINE)
        return [match.group(1).strip() for match in pattern.finditer(expanded_tex)]

    def _split_markdown_chunks(self, markdown: str) -> List[Tuple[str, str]]:
        lines = markdown.splitlines()
        chunks: List[Tuple[str, List[str]]] = []
        current_title = "Document"
        current_lines: List[str] = []
        for line in lines:
            if line.startswith("# "):
                if current_lines:
                    chunks.append((current_title, current_lines))
                    current_lines = []
                current_title = line.lstrip("# ").strip() or current_title
            current_lines.append(line)
        if current_lines:
            chunks.append((current_title, current_lines))
        return [(title, "\n".join(content).strip()) for title, content in chunks if content]

    def _write_macros(self, macros: List[str], target_dir: Path) -> Path:
        macros_path = target_dir / "macros.md"
        if not macros:
            macros_path.write_text("(No macro definitions found.)\n", encoding="utf-8")
            return macros_path
        lines = ["# Macro Definitions", "", "```tex"] + macros + ["```", ""]
        macros_path.write_text("\n".join(lines), encoding="utf-8")
        return macros_path

    def _write_chunks(self, chunks: List[Tuple[str, str]], target_dir: Path) -> Path:
        chunks_dir = target_dir / "chunks"
        chunks_dir.mkdir(exist_ok=True)
        index: List[Dict] = []
        for idx, (title, content) in enumerate(chunks):
            chunk_path = chunks_dir / f"{idx:02d}.md"
            chunk_path.write_text(content + "\n", encoding="utf-8")
            index.append(
                {
                    "id": idx,
                    "title": title,
                    "path": self._relativize(chunk_path, self.processed_dir.parent),
                    "char_count": len(content),
                }
            )
        index_path = target_dir / "chunks.yaml"
        with index_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(index, handle, allow_unicode=True, sort_keys=False)
        return index_path

    # ------------------------------------------------------------------
    # Common helpers

    def _compose_markdown(self, metadata: Dict, paper_body: str) -> str:
        header_lines = [
            "---",
            f"title: {metadata.get('title', '')}",
            f"authors: {metadata.get('authors', [])}",
            f"year: {metadata.get('year') or ''}",
            f"doi: {metadata.get('doi') or ''}",
            "ingested_at: " + datetime.now(timezone.utc).isoformat(),
            "---",
            "",
        ]
        return "\n".join(header_lines) + paper_body + "\n"

    def _build_metadata_payload(
        self,
        slug: str,
        metadata: Dict,
        source_path: Path,
        paper_path: Path,
        *,
        source_type: str,
        extra: Dict,
    ) -> Dict:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": slug,
            "title": metadata.get("title"),
            "authors": metadata.get("authors", []),
            "year": metadata.get("year"),
            "doi": metadata.get("doi"),
            "source_path": self._relativize(source_path, self.raw_dir.parent),
            "paper_path": self._relativize(paper_path, self.processed_dir.parent),
            "summary_path": self._relativize(paper_path.parent / "summary.md", self.processed_dir.parent),
            "summary_alias_path": self._relativize(
                self.summaries_dir / f"{slug}.md", self.summaries_dir.parent
            ),
            "ingested_at": now,
            "tags": metadata.get("tags", []),
            "summary_generated": False,
            "source_type": source_type,
        }
        payload.update(extra)
        return payload

    def _update_index(self, entry: Dict) -> None:
        if self.index_path.exists():
            with self.index_path.open("r", encoding="utf-8") as handle:
                try:
                    data = yaml.safe_load(handle) or []
                except yaml.YAMLError:
                    data = []
        else:
            data = []

        data = [item for item in data if item.get("id") != entry["id"]]
        data.append(entry)
        data.sort(key=lambda item: item.get("ingested_at", ""))

        with self.index_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)

        self._update_summary_index(entry)

    def _update_summary_index(self, entry: Dict) -> None:
        existing: List[Dict]
        if self.summary_index_path.exists():
            try:
                existing = json.loads(self.summary_index_path.read_text(encoding="utf-8")) or []
            except (json.JSONDecodeError, OSError):
                existing = []
        else:
            existing = []

        existing = [item for item in existing if item.get("id") != entry.get("id")]

        if entry.get("summary_generated"):
            payload = {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "summary_path": entry.get("summary_path"),
                "summary_alias_path": entry.get("summary_alias_path"),
                "source_type": entry.get("source_type"),
                "tags": entry.get("tags", []),
                "updated_at": entry.get("summary_updated_at") or entry.get("ingested_at"),
            }
            existing.append(payload)

        existing.sort(key=lambda item: item.get("updated_at", ""))

        self.summary_index_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _relativize(self, path: Path, base: Path) -> str:
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    def _sync_summary_alias(self, summary_path: Path, slug: str) -> Path:
        alias_path = self.summaries_dir / f"{slug}.md"
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()
        try:
            relative_target = os.path.relpath(summary_path, alias_path.parent)
            alias_path.symlink_to(relative_target)
        except (OSError, NotImplementedError, ValueError):
            shutil.copy2(summary_path, alias_path)
        return alias_path

    def _remove_summary_alias(self, slug: str) -> None:
        alias_path = self.summaries_dir / f"{slug}.md"
        try:
            if alias_path.exists() or alias_path.is_symlink():
                alias_path.unlink()
        except OSError:
            pass

    def _is_ingestion_complete(self, target_dir: Path) -> bool:
        paper_path = target_dir / "paper.md"
        metadata_path = target_dir / "metadata.yaml"
        if not paper_path.exists() or not metadata_path.exists():
            return False
        if paper_path.stat().st_size == 0:
            return False
        return True

    def _load_existing_metadata(self, target_dir: Path) -> Dict:
        metadata_path = target_dir / "metadata.yaml"
        if metadata_path.exists():
            try:
                return yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                return {}
        return {}

    def _build_existing_result(
        self,
        slug: str,
        source_path: Path,
        target_dir: Path,
    ) -> IngestionResult:
        metadata = self._load_existing_metadata(target_dir)
        title = metadata.get("title") or slug
        message = f"Skipped ingestion for '{title}' (existing artifacts found)."
        paper_path = target_dir / "paper.md"
        summary_path = target_dir / "summary.md"
        metadata_path = target_dir / "metadata.yaml"
        return IngestionResult(
            slug=slug,
            paper_path=paper_path,
            summary_path=summary_path,
            summary_alias_path=self.summaries_dir / f"{slug}.md",
            metadata_path=metadata_path,
            source_path=source_path,
            message=message,
        )

    def _build_slug(self, metadata: Dict, fallback_name: str) -> str:
        year = metadata.get("year")
        title_fragment = self._slugify(metadata.get("title") or fallback_name)
        prefix = f"{year}-" if year else ""
        base_slug = (prefix + title_fragment)[:64].rstrip("-") or self._slugify(fallback_name)
        return base_slug

    def _slugify(self, value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = value.strip("-")
        return value or "document"

    def _extract_braced_value(self, text: str, command: str) -> Optional[str]:
        pattern = re.compile(r"\\" + command + r"\s*\{")
        match = pattern.search(text)
        if not match:
            return None

        start = match.end()
        depth = 1
        pos = start
        length = len(text)
        while pos < length and depth > 0:
            char = text[pos]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            pos += 1

        if depth != 0:
            return None

        return text[start : pos - 1]

    def _strip_latex(self, value: str) -> str:
        if not value:
            return ""

        text = re.sub(r"%.*$", "", value, flags=re.MULTILINE)
        text = re.sub(r"\\(IEEEauthorrefmark|thanks|footnote)\s*\{[^}]*\}", "", text)

        if LATEX_TO_TEXT is not None:
            cleaned = LATEX_TO_TEXT.latex_to_text(text)
        else:
            def replacer(match) -> str:
                content = match.group(1)
                if content:
                    return content.strip()
                return ""

            cleaned = re.sub(r"\\[a-zA-Z@]+\*?(?:\s*\{([^{}]*)\})?", replacer, text)
            cleaned = cleaned.replace("\\\\", " ")
            cleaned = cleaned.replace("\\", " ")
            cleaned = cleaned.replace("{", "").replace("}", "")

        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip().strip("-:_ ")

    # ------------------------------------------------------------------
    # Summary generation

    def ensure_summary(
        self,
        slug: str,
        *,
        force: bool = False,
    ) -> SummaryGenerationResult:
        target_dir = self.processed_dir / slug
        if not target_dir.exists():
            raise DocumentIngestionError(f"Ingested slug not found: {slug}")

        paper_path = target_dir / "paper.md"
        if not paper_path.exists():
            raise DocumentIngestionError(f"paper.md not found for slug '{slug}'. Run ingest first.")

        summary_path = target_dir / "summary.md"

        metadata_path = target_dir / "metadata.yaml"
        metadata: Dict = {}
        if metadata_path.exists():
            try:
                metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise DocumentIngestionError(f"Failed to parse metadata.yaml for '{slug}': {exc}")

        if summary_path.exists() and not force:
            alias_path = self._sync_summary_alias(summary_path, slug)
            self._persist_summary_metadata(
                metadata,
                slug,
                summary_path,
                alias_path,
                metadata_path,
                update_timestamp=False,
            )
            return SummaryGenerationResult(
                slug=slug,
                summary_path=summary_path,
                summary_alias_path=alias_path,
                regenerated=False,
            )

        summary_text = self._run_summary_command(slug, metadata, paper_path)
        if not summary_text.strip():
            raise DocumentIngestionError(
                f"Codex summary command returned empty output for '{slug}'."
            )

        summary_path.write_text(summary_text.strip() + "\n", encoding="utf-8")

        alias_path = self._sync_summary_alias(summary_path, slug)
        self._persist_summary_metadata(
            metadata,
            slug,
            summary_path,
            alias_path,
            metadata_path,
            update_timestamp=True,
        )

        return SummaryGenerationResult(
            slug=slug,
            summary_path=summary_path,
            summary_alias_path=alias_path,
            regenerated=True,
        )

    def _run_summary_command(self, slug: str, metadata: Dict, paper_path: Path) -> str:
        command = [
            str(part).format(
                slug=slug,
                paper_path=str(paper_path),
                metadata_path=str(paper_path.parent / "metadata.yaml"),
            )
            for part in self.summary_command
        ]

        try:
            paper_body = paper_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DocumentIngestionError(f"Failed to read paper.md for '{slug}': {exc}") from exc

        env = os.environ.copy()
        env.setdefault("CODEX_SUMMARY_SLUG", slug)
        env.setdefault("CODEX_SUMMARY_TITLE", (metadata.get("title") or slug))
        env.setdefault("CODEX_SUMMARY_SOURCE_TYPE", metadata.get("source_type", ""))

        try:
            result = subprocess.run(
                command,
                input=paper_body,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise DocumentIngestionError(
                f"Summary command not found: {command[0]}"
            ) from exc
        except Exception as exc:  # pragma: no cover - unexpected subprocess errors
            raise DocumentIngestionError(f"Failed to execute summary command: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise DocumentIngestionError(
                f"Summary command exited with status {result.returncode}: {stderr}"
            )

        return (result.stdout or "").strip()

    def _persist_summary_metadata(
        self,
        metadata: Dict,
        slug: str,
        summary_path: Path,
        alias_path: Path,
        metadata_path: Path,
        *,
        update_timestamp: bool,
    ) -> None:
        metadata.setdefault("id", slug)
        metadata["summary_generated"] = True
        if update_timestamp or not metadata.get("summary_updated_at"):
            metadata["summary_updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata["summary_path"] = self._relativize(summary_path, self.processed_dir.parent)
        metadata["summary_alias_path"] = self._relativize(alias_path, self.summaries_dir.parent)

        with metadata_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(metadata, handle, allow_unicode=True, sort_keys=False)

        self._update_index(metadata)
