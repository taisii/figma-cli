import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml
from pypdf import PdfReader

from .llm_client import LLMUnavailableError, build_generative_model


class PDFIngestionError(Exception):
    """Raised when a PDF cannot be processed."""


@dataclass
class IngestionResult:
    slug: str
    paper_path: Path
    summary_path: Path
    metadata_path: Path
    source_pdf: Path
    message: str


class PDFIngestor:
    """Handle PDF ingestion via Nougat and optional Gemini summarisation."""

    def __init__(self, config: Dict, llm_model_override: Optional[str] = None):
        self.config = config
        ingestion_cfg = config.get("pdf_ingest", {})
        self.raw_dir = Path(ingestion_cfg.get("raw_dir", "context/papers/raw"))
        self.processed_dir = Path(ingestion_cfg.get("processed_dir", "context/papers"))
        self.index_path = Path(ingestion_cfg.get("index_path", "context/index.yaml"))
        self.nougat_model = ingestion_cfg.get("nougat_model")
        self.summary_max_chars = ingestion_cfg.get("summary_max_chars", 12000)

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        self._llm = None
        self._llm_error: Optional[Exception] = None
        self._llm_model_override = llm_model_override

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
            raise PDFIngestionError(f"PDF not found: {pdf_path}")

        if pdf_path.suffix.lower() != ".pdf":
            raise PDFIngestionError("Only .pdf files are supported.")

        raw_pdf_path = self._prepare_raw_pdf(pdf_path, copy_to_raw)

        metadata = self._extract_metadata(raw_pdf_path)
        slug_value = slug or self._build_slug(metadata, raw_pdf_path)
        target_dir = self.processed_dir / slug_value

        if target_dir.exists():
            if not force:
                raise PDFIngestionError(
                    f"Ingestion target '{slug_value}' already exists. Use --force to overwrite."
                )
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        nougat_markdown = self._convert_with_nougat(raw_pdf_path)

        paper_body = nougat_markdown.strip()
        paper_content = self._compose_markdown(metadata, paper_body)

        paper_path = target_dir / "paper.md"
        paper_path.write_text(paper_content, encoding="utf-8")

        metadata_payload = self._build_metadata_payload(
            slug_value,
            metadata,
            raw_pdf_path,
            paper_path,
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
            metadata_path=metadata_path,
            source_pdf=raw_pdf_path,
            message=message,
        )

    def ingest_all_pending(self, *, force: bool = False) -> Sequence[IngestionResult]:
        pdf_files = sorted(self.raw_dir.glob("*.pdf"))
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
            except PDFIngestionError as exc:
                errors.append(f"{pdf_file.name}: {exc}")

        if errors:
            raise PDFIngestionError("\n".join(errors))

        if not results:
            raise PDFIngestionError("No PDFs found in the raw inbox.")

        return results

    # --- Private helpers -------------------------------------------------

    def _prepare_raw_pdf(self, pdf_path: Path, copy_to_raw: bool) -> Path:
        if copy_to_raw:
            destination = (self.raw_dir / pdf_path.name).resolve()
            if pdf_path != destination:
                shutil.copy2(pdf_path, destination)
            return destination
        return pdf_path

    def _extract_metadata(self, pdf_path: Path) -> Dict:
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

    def _parse_pdf_year(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        match = re.search(r"(19|20)\d{2}", str(value))
        if match:
            return match.group(0)
        return None

    def _build_slug(self, metadata: Dict, pdf_path: Path) -> str:
        year = metadata.get("year")
        title_fragment = self._slugify(metadata.get("title") or pdf_path.stem)
        prefix = f"{year}-" if year else ""
        base_slug = (prefix + title_fragment)[:64].rstrip("-") or self._slugify(pdf_path.stem)

        slug = base_slug
        counter = 2
        while (self.processed_dir / slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def _slugify(self, value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = value.strip("-")
        return value or "paper"

    def _convert_with_nougat(self, pdf_path: Path) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            command = ["nougat", str(pdf_path), "--out", str(output_dir)]
            if self.nougat_model:
                command.extend(["--model", str(self.nougat_model)])

            try:
                completed = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise PDFIngestionError(
                    "Nougat CLI is not installed or not found in PATH."
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip() if exc.stderr else exc.stdout
                raise PDFIngestionError(f"Nougat conversion failed: {stderr}") from exc

            generated_files = list(output_dir.glob("*.md")) or list(output_dir.glob("*.mmd"))
            if not generated_files:
                raise PDFIngestionError(
                    "Nougat did not produce a Markdown file. Check the PDF and Nougat output."
                )

            content = generated_files[0].read_text(encoding="utf-8")
            if completed.stdout:
                self._write_conversion_log(pdf_path, completed.stdout)

        return content

    def _write_conversion_log(self, pdf_path: Path, stdout: str) -> None:
        log_dir = self.raw_dir
        log_path = log_dir / f"{pdf_path.stem}.log"
        log_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stdout": stdout,
        }
        log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def _build_summary_prompt(self, metadata: Dict, paper_content: str) -> str:
        title = metadata.get("title", "Unknown Title")
        authors = ", ".join(metadata.get("authors", [])) or metadata.get("author", "")
        published = metadata.get("year")
        doi = metadata.get("doi")

        meta_lines = [f"タイトル: {title}"]
        if authors:
            meta_lines.append(f"著者: {authors}")
        if published:
            meta_lines.append(f"発行年: {published}")
        if doi:
            meta_lines.append(f"DOI: {doi}")

        prompt_parts = [
            "あなたは研究支援を担当する優秀なアシスタントです。",
            "以下の論文本文を読み込み、研究概要を日本語でまとめてください。",
            "サマリーは次の見出しを含めたマークダウンで出力してください:",
            "",
            "# 概要",
            "## 背景",
            "## 問題設定",
            "## 手法",
            "## 実験・結果",
            "## 考察・含意",
            "## キーワード (箇条書き)",
            "",
            "必要であれば本文の重要な引用をインラインで引用してください。",
            "",
            "--- 論文メタ情報 ---",
            "\n".join(meta_lines),
            "",
            "--- 論文本文 (Markdown) ---",
            paper_content,
            "",
            "上記を踏まえて、指定した構成でサマリーを書いてください。"
        ]
        return "\n".join(prompt_parts)

    def _build_metadata_payload(
        self,
        slug: str,
        metadata: Dict,
        pdf_path: Path,
        paper_path: Path,
    ) -> Dict:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": slug,
            "title": metadata.get("title"),
            "authors": metadata.get("authors", []),
            "year": metadata.get("year"),
            "doi": metadata.get("doi"),
            "source_pdf": self._relativize(pdf_path, self.raw_dir.parent),
            "paper_path": self._relativize(paper_path, self.processed_dir.parent),
            "summary_path": self._relativize(paper_path.parent / "summary.md", self.processed_dir.parent),
            "ingested_at": now,
            "tags": metadata.get("tags", []),
            "summary_generated": False,
        }
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

    def _relativize(self, path: Path, base: Path) -> str:
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    # --- Summary generation -------------------------------------------------

    def ensure_summary(
        self,
        slug: str,
        *,
        force: bool = False,
        llm_model_override: Optional[str] = None,
    ) -> Path:
        """Generate (or regenerate) a summary for the specified paper slug."""

        target_dir = self.processed_dir / slug
        if not target_dir.exists():
            raise PDFIngestionError(f"Ingested paper slug not found: {slug}")

        paper_path = target_dir / "paper.md"
        if not paper_path.exists():
            raise PDFIngestionError(f"paper.md not found for slug '{slug}'. Run ingest first.")

        summary_path = target_dir / "summary.md"
        if summary_path.exists() and not force:
            raise PDFIngestionError(
                f"summary.md already exists for '{slug}'. Use --force to overwrite."
            )

        metadata_path = target_dir / "metadata.yaml"
        metadata: Dict = {}
        if metadata_path.exists():
            try:
                metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise PDFIngestionError(f"Failed to parse metadata.yaml for '{slug}': {exc}")

        paper_body = paper_path.read_text(encoding="utf-8")
        excerpt = paper_body
        if len(excerpt) > self.summary_max_chars:
            excerpt = excerpt[: self.summary_max_chars]

        llm_client = self._get_llm(model_override=llm_model_override)

        prompt = self._build_summary_prompt(metadata, excerpt)
        try:
            response = llm_client.generate_content(prompt)
            summary_text = (response.text or "").strip()
        except Exception as exc:  # pragma: no cover - external SDK failure path
            raise PDFIngestionError(f"Gemini summary generation failed: {exc}") from exc

        summary_path.write_text(summary_text, encoding="utf-8")

        metadata.setdefault("id", slug)
        metadata["summary_generated"] = True
        metadata["summary_updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata["summary_path"] = self._relativize(summary_path, self.processed_dir.parent)

        with metadata_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(metadata, handle, allow_unicode=True, sort_keys=False)

        self._update_index(metadata)

        return summary_path

    def _get_llm(self, model_override: Optional[str] = None):
        model_id = model_override or self._llm_model_override
        if self._llm and model_id == self._llm_model_override:
            return self._llm

        try:
            self._llm = build_generative_model(
                self.config,
                model_name_override=model_id,
            )
            self._llm_error = None
            self._llm_model_override = model_id
            return self._llm
        except LLMUnavailableError as exc:
            self._llm_error = exc
            raise PDFIngestionError(str(exc)) from exc
