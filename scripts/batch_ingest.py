#!/usr/bin/env python3
"""Batch-ingest text/markdown files via the RAG ingest pipeline.

Example::

    uv run python scripts/batch_ingest.py sample_docs/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from rag.ingest import ingest_document  # noqa: E402


def document_id_for(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return relative.with_suffix("").as_posix().replace("/", "__")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch ingest docs into Databricks RAG.")
    parser.add_argument("directory", type=Path, help="Folder with .txt or .md files")
    args = parser.parse_args()

    directory = args.directory.resolve()
    if not directory.is_dir():
        print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        return 1

    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}
    )
    if not files:
        print(f"No .txt or .md files under {directory}", file=sys.stderr)
        return 1

    total_chunks = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        doc_id = document_id_for(path, directory)
        chunks, _ = ingest_document(
            document_id=doc_id,
            text=text,
            source=path.name,
        )
        total_chunks += chunks
        print(f"{doc_id}: {chunks} chunks")

    print(f"\nDone. {len(files)} files, {total_chunks} total chunks indexed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
