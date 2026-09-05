"""Batch-ingest local text files into Pinecone via the ingest helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from rag.ingest import ingest_document

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest docs into Pinecone RAG.")
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Text files to ingest (document_id = file stem).",
    )
    args = parser.parse_args()

    for path in args.paths:
        text = path.read_text(encoding="utf-8")
        chunks, tokens = ingest_document(
            document_id=path.stem,
            text=text,
            source=str(path),
        )
        print(f"{path.name}: chunks={chunks} embedding_tokens={tokens}")


if __name__ == "__main__":
    main()
