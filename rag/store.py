"""Write embedded chunks to the Unity Catalog Delta source table."""

from __future__ import annotations

import os
from functools import lru_cache

from databricks.connect import DatabricksSession
from pyspark.sql import Row
from pyspark.sql.types import ArrayType, FloatType, IntegerType, StringType, StructField, StructType

from rag.config import load_rag_config

CHUNK_SCHEMA = StructType(
    [
        StructField("id", StringType(), nullable=False),
        StructField("document_id", StringType(), nullable=False),
        StructField("chunk_index", IntegerType(), nullable=False),
        StructField("chunk_text", StringType(), nullable=False),
        StructField("source", StringType(), nullable=True),
        StructField("text_vector", ArrayType(FloatType()), nullable=True),
    ]
)


@lru_cache(maxsize=1)
def get_spark():
    """Return a Databricks Connect Spark session (local profile or app runtime)."""
    profile = os.getenv("DATABRICKS_CONFIG_PROFILE")
    builder = DatabricksSession.builder
    if profile:
        builder = builder.profile(profile)
    return builder.serverless().getOrCreate()


def delete_document_chunks(document_id: str) -> None:
    """Remove existing chunks for ``document_id`` before re-ingest."""
    config = load_rag_config()
    spark = get_spark()
    escaped = document_id.replace("'", "''")
    spark.sql(
        f"DELETE FROM {config.full_table_name} WHERE document_id = '{escaped}'"
    )


def append_chunks(
    document_id: str,
    chunks: list[str],
    vectors: list[list[float]],
    source: str | None = None,
) -> int:
    """Append chunked rows with embeddings to the Delta table."""
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")

    config = load_rag_config()
    rows = [
        Row(
            id=f"{document_id}::{index}",
            document_id=document_id,
            chunk_index=index,
            chunk_text=chunk_text,
            source=source,
            text_vector=vector,
        )
        for index, (chunk_text, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    if not rows:
        return 0

    spark = get_spark()
    (
        spark.createDataFrame(rows, schema=CHUNK_SCHEMA)
        .write.format("delta")
        .mode("append")
        .saveAsTable(config.full_table_name)
    )
    return len(rows)
