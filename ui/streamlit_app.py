"""Streamlit UI for Session 2 RAG — calls the FastAPI service (no RAG logic here)."""

from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="RAG Demo", layout="wide")
st.title("Session 2 RAG Demo")
st.caption("Ingest documents and ask questions via your FastAPI service.")

api_url = st.sidebar.text_input("API base URL", DEFAULT_API_URL.rstrip("/"))
st.sidebar.caption(
    "Default is local API. After Render deploy, paste your public URL here."
)

ingest_tab, ask_tab, debug_tab = st.tabs(["Ingest", "Ask", "Debug retrieve"])

with ingest_tab:
    document_id = st.text_input("document_id", value="handbook")
    source = st.text_input("source (optional)", value="")
    text = st.text_area("Text to ingest", height=200)
    if st.button("Ingest", type="primary"):
        payload = {"text": text, "document_id": document_id}
        if source.strip():
            payload["source"] = source.strip()
        try:
            response = httpx.post(f"{api_url}/ingest", json=payload, timeout=120.0)
            response.raise_for_status()
            st.success(response.json())
        except httpx.HTTPError as exc:
            st.error(f"Ingest failed: {exc}")

with ask_tab:
    question = st.text_input("Question", value="What is the remote work policy?")
    if st.button("Ask", type="primary"):
        try:
            response = httpx.post(
                f"{api_url}/ask",
                json={"question": question},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            st.subheader("Answer")
            st.write(data.get("answer"))
            cols = st.columns(4)
            cols[0].metric("tokens_used", data.get("tokens_used"))
            cols[1].metric("cost_usd", data.get("cost_usd"))
            cols[2].metric("confidence", data.get("confidence_score"))
            cols[3].metric("refused", str(data.get("refused")))
            st.write("citations:", data.get("citations"))
            st.write(
                "cited_chunk_ids:",
                data.get("cited_chunk_ids") or data.get("retrieved_chunk_ids"),
            )
            with st.expander("Full JSON"):
                st.json(data)
        except httpx.HTTPError as exc:
            st.error(f"Ask failed: {exc}")

with debug_tab:
    q = st.text_input("Retrieve query", value="remote work policy", key="debug_q")
    if st.button("Retrieve", type="primary"):
        try:
            response = httpx.get(
                f"{api_url}/debug/retrieve",
                params={"q": q},
                timeout=60.0,
            )
            response.raise_for_status()
            st.json(response.json())
        except httpx.HTTPError as exc:
            st.error(f"Retrieve failed: {exc}")
