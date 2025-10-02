#!/usr/bin/env python
"""Codex CLI entrypoint for research support utilities."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import yaml

from src.document_ingestor import DocumentIngestor, DocumentIngestionError


def load_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}


def ingest_pdf_command(args: argparse.Namespace) -> int:
    config = load_config()
    ingestor = DocumentIngestor(config, llm_model_override=args.llm_model)

    try:
        if args.path:
            result = ingestor.ingest_pdf(
                Path(args.path),
                force=args.force,
                copy_to_raw=not args.no_copy,
                slug=args.slug,
            )
            print(result.message)
            print(f"  paper:   {result.paper_path}")
            print(f"  summary (pending): {result.summary_path}")
            print(f"  meta:    {result.metadata_path}")
            print("Use 'python codex_cli.py summarize paper <slug>' to generate a summary when ready.")
            return 0

        results = ingestor.ingest_all_pending(force=args.force)
        for item in results:
            print(item.message)
            print(f"  paper:   {item.paper_path}")
            print(f"  summary (pending): {item.summary_path}")
            print(f"  meta:    {item.metadata_path}")
        if results:
            print("Use 'python codex_cli.py summarize paper <slug>' to generate summaries when needed.")
        return 0
    except DocumentIngestionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def summarize_paper_command(args: argparse.Namespace) -> int:
    config = load_config()
    ingestor = DocumentIngestor(config)

    try:
        summary_path = ingestor.ensure_summary(
            args.slug,
            force=args.force,
            llm_model_override=args.llm_model,
        )
        print(f"Generated summary: {summary_path}")
        return 0
    except DocumentIngestionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def ingest_tex_command(args: argparse.Namespace) -> int:
    config = load_config()
    ingestor = DocumentIngestor(config, llm_model_override=args.llm_model)

    try:
        result = ingestor.ingest_tex_folder(
            Path(args.path),
            root_file=args.root,
            force=args.force,
            copy_to_raw=not args.no_copy,
            slug=args.slug,
        )
        print(result.message)
        print(f"  paper:   {result.paper_path}")
        print(f"  summary (pending): {result.summary_path}")
        print(f"  meta:    {result.metadata_path}")
        print(f"  source:  {result.source_path}")
        return 0
    except DocumentIngestionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex", description="Codex CLI utilities")
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest content into the knowledge base")
    ingest_subparsers = ingest_parser.add_subparsers(dest="resource")

    pdf_parser = ingest_subparsers.add_parser(
        "pdf",
        help="Convert a PDF to Markdown and generate related artifacts",
    )
    pdf_parser.add_argument("path", nargs="?", help="Path to the PDF file. If omitted, process all PDFs in the raw inbox.")
    pdf_parser.add_argument("--slug", help="Explicit slug name for the ingested paper.")
    pdf_parser.add_argument("--force", action="store_true", help="Overwrite existing ingested content with the same slug.")
    pdf_parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Use the PDF in-place instead of copying it into the raw inbox.",
    )
    pdf_parser.add_argument(
        "--llm-model",
        help="Gemini model id override for summary generation.",
    )
    pdf_parser.set_defaults(func=ingest_pdf_command)

    tex_parser = ingest_subparsers.add_parser(
        "tex",
        help="Convert a TeX project into Markdown and related artifacts.",
    )
    tex_parser.add_argument("path", help="Path to the TeX project directory.")
    tex_parser.add_argument("--root", help="Entry-point TeX filename if autodetection fails.")
    tex_parser.add_argument("--slug", help="Explicit slug name for the ingested project.")
    tex_parser.add_argument("--force", action="store_true", help="Overwrite existing ingested content with the same slug.")
    tex_parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Use the TeX project in-place instead of copying it into the raw inbox.",
    )
    tex_parser.add_argument(
        "--llm-model",
        help="Gemini model id override for summary generation.",
    )
    tex_parser.set_defaults(func=ingest_tex_command)

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Generate supplemental artifacts from ingested content",
    )
    summarize_subparsers = summarize_parser.add_subparsers(dest="resource")

    summarize_pdf_parser = summarize_subparsers.add_parser(
        "paper",
        help="Summarize an ingested paper using Gemini",
    )
    summarize_pdf_parser.add_argument("slug", help="Slug of the ingested paper to summarise.")
    summarize_pdf_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing summary.",
    )
    summarize_pdf_parser.add_argument(
        "--llm-model",
        help="Gemini model id override for this summary generation.",
    )
    summarize_pdf_parser.set_defaults(func=summarize_paper_command)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
