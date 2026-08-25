"""Create Unity Catalog objects for Session 2 RAG (Phase 0.3).

Naming convention (override any default via env vars):

  workspace.document_retrieval.document_chunks        Delta source table
  workspace.document_retrieval.document_chunks_index  AI Search index (Phase 0.5)
  document-chunks-search-endpoint                     AI Search endpoint (Phase 0.4)

The Delta table stores chunked, embedded text from POST /ingest. The AI Search
index (created later in the UI) syncs from this table for similarity search.
"""

import os
import sys

from databricks.connect import DatabricksSession

# Unity Catalog — three-level names
CATALOG = os.getenv("RAG_CATALOG", "workspace")
SCHEMA = os.getenv("RAG_SCHEMA", "document_retrieval")
TABLE_NAME = os.getenv("RAG_TABLE", "document_chunks")
FULL_TABLE_NAME = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"

# Related AI Search objects (created in Phase 0.4 / 0.5 — documented for consistency)
VECTOR_SEARCH_ENDPOINT = os.getenv(
    "VECTOR_SEARCH_ENDPOINT", "document-chunks-search-endpoint"
)
VECTOR_SEARCH_INDEX = os.getenv(
    "VECTOR_SEARCH_INDEX",
    f"{CATALOG}.{SCHEMA}.{TABLE_NAME}_index",
)

PROFILE = os.getenv("DATABRICKS_CONFIG_PROFILE", "dbx-lzago-ai")


def main() -> None:
    print(f"Connecting with profile: {PROFILE}")
    print(f"Target table: {FULL_TABLE_NAME}")
    print(f"Future index:  {VECTOR_SEARCH_INDEX}")
    print(f"Future endpoint: {VECTOR_SEARCH_ENDPOINT}")

    spark = (
        DatabricksSession.builder.profile(PROFILE)
        .serverless()
        .getOrCreate()
    )

    print("\nCreating schema...")
    spark.sql(
        f"""
        CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}
        COMMENT 'RAG document chunks and embeddings for the /ask service'
        """
    )

    print("Creating Delta table...")
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {FULL_TABLE_NAME} (
          id STRING NOT NULL,
          document_id STRING NOT NULL,
          chunk_index INT NOT NULL,
          chunk_text STRING NOT NULL,
          source STRING,
          text_vector ARRAY<FLOAT>
        )
        USING DELTA
        COMMENT 'Embedded document chunks; source for Delta Sync AI Search index'
        """
    )

    print("Enabling Change Data Feed...")
    spark.sql(
        f"""
        ALTER TABLE {FULL_TABLE_NAME}
        SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
        """
    )

    print("\n--- Verification ---")
    spark.sql(f"DESCRIBE TABLE EXTENDED {FULL_TABLE_NAME}").show(200, truncate=False)
    spark.sql(f"SHOW TBLPROPERTIES {FULL_TABLE_NAME}").filter(
        "key = 'delta.enableChangeDataFeed'"
    ).show(truncate=False)

    row_count = spark.table(FULL_TABLE_NAME).count()
    print(f"\nTable {FULL_TABLE_NAME} ready. Row count: {row_count}")
    print("Phase 0.3 complete.")
    print("\nNext (Phase 0.4–0.5 in Databricks UI):")
    print(f"  1. Create endpoint: {VECTOR_SEARCH_ENDPOINT}")
    print(f"  2. Create Delta Sync index: {VECTOR_SEARCH_INDEX}")
    print(f"     Source table: {FULL_TABLE_NAME}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
