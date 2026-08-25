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
st.sidebar.markdown("Set `API_URL` in `.env` for your Databricks App URL.")

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
    model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "o3-mini"])
    if st.button("Ask", type="primary"):
        try:
            response = httpx.post(
                f"{api_url}/ask",
                json={"question": question, "model": model},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            st.subheader("Answer")
            st.write(data.get("answer"))
            if data.get("refused"):
                st.warning("Refusal response")
            st.markdown("**Citations (document_id):** " + ", ".join(data.get("citations", [])))
            st.markdown("**Retrieved chunk IDs:**")
            st.code("\n".join(data.get("retrieved_chunk_ids", [])) or "(none)")
            with st.expander("Full JSON"):
                st.json(data)
        except httpx.HTTPError as exc:
            st.error(f"Ask failed: {exc}")

with debug_tab:
    debug_q = st.text_input("Debug question", value="What is the remote work policy?")
    if st.button("Retrieve only"):
        try:
            response = httpx.get(
                f"{api_url}/debug/retrieve",
                params={"q": debug_q},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            for chunk in data.get("chunks", []):
                st.markdown(f"**{chunk['id']}** (score={chunk.get('score')})")
                st.write(chunk.get("chunk_text"))
                st.divider()
        except httpx.HTTPError as exc:
            st.error(f"Retrieve failed: {exc}")
