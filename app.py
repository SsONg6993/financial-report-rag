"""Run with: streamlit run app.py"""

import os
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from qdrant_client import QdrantClient

from src.chunker import chunk_filing
from src.embeddings import Embeddings
from src.llm import generate_answer
from src.parser import parse_filing
from src.retriever import Retriever, collection_name
from src.sec import download_filing, list_annual_filings, normalize_ticker


load_dotenv()
st.set_page_config(page_title="Financial Report Intelligence", layout="wide")
st.title("Financial Report Intelligence")
st.caption("Ask questions about an annual SEC filing. Answers use retrieved excerpts from that filing.")


@st.cache_resource
def get_embeddings(model_name: str) -> Embeddings:
    return Embeddings(model_name)


@st.cache_resource
def get_qdrant_client() -> QdrantClient:
    # Qdrant local mode holds a file lock, so share one client across reruns and models.
    return QdrantClient(path="data/vector_store")


@st.cache_resource
def get_retriever(model_name: str) -> Retriever:
    return Retriever(get_embeddings(model_name), client=get_qdrant_client())


with st.sidebar:
    ticker_input = st.text_input("Stock ticker", value="AAPL")
    load_clicked = st.button("Load annual filings")
    embedding_model = st.text_input("Embedding model", value=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
    ollama_model = st.text_input("Ollama model", value=os.getenv("OLLAMA_MODEL", "llama3.2"))
    top_k = st.slider("Top K excerpts", 1, 10, 5)

if load_clicked:
    try:
        with st.spinner("Loading SEC submissions..."):
            st.session_state.filings = list_annual_filings(ticker_input)
            st.session_state.loaded_ticker = normalize_ticker(ticker_input)
    except (ValueError, requests.RequestException, KeyError) as exc:
        st.error(f"Could not load filings: {exc}")

filings = st.session_state.get("filings", [])
if filings:
    filing = st.selectbox(
        "Annual filing",
        filings,
        format_func=lambda item: (
            f"{item['form']} | year ended {item['report_date']} | filed {item['filing_date']}"
        ),
    )
    st.subheader(f"{filing['company']} ({filing['ticker']})")
    st.write(f"**Form:** {filing['form']}  |  **Report year:** {filing['year']}  |  "
             f"**Filed:** {filing['filing_date']}")
    st.link_button("Open SEC filing", filing["source_url"])

    name = collection_name(filing, embedding_model)
    if st.button("Process / index filing"):
        try:
            with st.spinner("Downloading, parsing and indexing the filing. The first run may take a few minutes..."):
                retriever = get_retriever(embedding_model)
                if retriever.has_index(name):
                    st.success("Existing index ready.")
                else:
                    html_path = download_filing(filing)
                    cleaned = parse_filing(html_path.read_text(encoding="utf-8", errors="replace"))
                    processed_path = Path("data/processed") / filing["ticker"] / str(filing["year"]) / "filing.txt"
                    processed_path.parent.mkdir(parents=True, exist_ok=True)
                    processed_path.write_text(cleaned, encoding="utf-8")
                    chunks = chunk_filing(cleaned, filing["ticker"], filing["year"], filing["form"])
                    retriever.build_index(name, chunks)
                    st.success(f"Indexed {len(chunks)} chunks.")
        except (ValueError, requests.RequestException, OSError, RuntimeError) as exc:
            st.error(f"Could not process the filing: {exc}")

    st.divider()
    question = st.text_input("Question about this filing", placeholder="What were the main risk factors?")
    if st.button("Ask", disabled=not question.strip()):
        try:
            retriever = get_retriever(embedding_model)
            if not retriever.has_index(name):
                st.warning("Process / index this filing first.")
            else:
                start = time.perf_counter()
                chunks = retriever.search(name, question.strip(), top_k)
                retrieval_time = time.perf_counter() - start
                context_chars = sum(len(chunk["text"]) for chunk in chunks)

                generation_time = 0.0
                try:
                    start = time.perf_counter()
                    answer = generate_answer(
                        question.strip(), chunks, ollama_model,
                        os.getenv("OLLAMA_URL", "http://localhost:11434"),
                    )
                    generation_time = time.perf_counter() - start
                    st.subheader("Answer")
                    st.write(answer)
                except (requests.RequestException, KeyError, ValueError) as exc:
                    generation_time = time.perf_counter() - start
                    st.info(f"Retrieval-only mode: Ollama is unavailable ({exc}).")

                st.subheader("Retrieved evidence")
                for index, chunk in enumerate(chunks, 1):
                    with st.expander(f"{index}. {chunk['section']} · similarity {chunk['score']:.3f}", expanded=index == 1):
                        st.write(chunk["text"])
                st.caption(
                    f"Retrieval: {retrieval_time:.2f}s · Generation: {generation_time:.2f}s · "
                    f"Chunks: {len(chunks)} · Approximate context: {context_chars:,} characters"
                )
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(f"Search failed: {exc}")
else:
    st.info("Enter a ticker and load its annual filings to begin.")
