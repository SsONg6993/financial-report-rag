# Financial Report Intelligence

A small learning project that finds annual SEC filings and answers questions using local semantic retrieval and, when available, a local Ollama model. It supports 10-K and 20-F filings.

## Architecture

```text
Ticker
↓
SEC EDGAR
↓
Filing HTML
↓
Parser
↓
Chunks
↓
Sentence Transformer
↓
Vector Store
↓
Query
↓
Top-K Retrieval
↓
Ollama
↓
Grounded Answer
```

`src/sec.py` lists and downloads filings. `parser.py` removes hidden metadata and cleans visible text. `chunker.py` creates overlapping chunks. `embeddings.py` uses Sentence Transformers. `retriever.py` stores and searches vectors in local Qdrant. `llm.py` calls Ollama. `app.py` is the Streamlit UI.

## Install

Use Python 3.12. From this directory:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

If you start from a fresh clone, edit `.env` and replace `SEC_USER_AGENT` with an identifying application name and your real contact email. The SEC expects automated clients to identify themselves. The first embedding run downloads the selected Sentence Transformer model. No LLM is downloaded by the app.

## Run

```powershell
streamlit run app.py
```

For Ollama answers, install [Ollama](https://ollama.com/download), start it, then explicitly pull the model named in `.env`, for example `ollama pull llama3.2`. If Ollama is absent, stopped, or the model is missing, retrieval still works and the UI shows the supporting chunks.

## Example workflow

1. Enter `AAPL`, then click **Load annual filings**.
2. Select a 10-K and click **Process / index filing**.
3. Ask, “What were the principal risks discussed in this report?”
4. Read the answer and expand the retrieved excerpts to inspect the evidence and similarity scores.

The app uses the SEC ticker list to find the CIK, then the company's submissions JSON to list recent 10-K and 20-F filings. It constructs the official EDGAR archive URL for the primary filing document. Downloads are cached under `data/raw/{ticker}/{year}/filing.html`; cleaned text goes to `data/processed`; Qdrant persists vectors in `data/vector_store`. Existing Qdrant collections are reused.

At query time, the question is embedded with the same model and compared with filing chunks using cosine similarity. The top K chunks are sent to Ollama as evidence. The prompt asks for section citations and an explicit insufficient-evidence answer. Source chunks remain visible for inspection.

## Tests

```powershell
pytest -q
```

## Known limitations and future improvements

- SEC submissions `recent` data is used, so older annual filings in pagination files are not listed.
- Section labels are approximate: repeated Item names in tables of contents may affect labels.
- HTML tables are flattened to text; complex multi-column layouts can lose structure.
- The simple year-based raw cache assumes one selected annual filing per ticker and report year.
- A CPU can take several minutes to embed a long filing on first use.
- Future work could add older submissions, better section detection, and richer table parsing after the baseline is understood.
