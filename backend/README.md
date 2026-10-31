# Yojana Sahayak backend

The backend contains the existing modular RAG pipeline, FastAPI adapter, source PDFs, and persisted Chroma database. Its runtime paths are resolved relative to this directory by `src/config.py`, independent of the current working directory.

## Setup

From the project root:

```powershell
Copy-Item backend\.env.example backend\.env
# Set GROQ_API_KEY in backend\.env
python -m pip install -r backend\requirements.txt
```

The `.env.example` contains placeholders only. `GROQ_API_KEY` is required for model responses. `CORS_ORIGINS` is a comma-separated list of allowed browser origins; it defaults to the local Vite origins.

Optional scheme discovery is disabled by default. Configure permitted government RSS/Atom feed URLs with comma-separated `SCHEME_DISCOVERY_FEEDS`; set `SCHEME_DISCOVERY_INTERVAL_HOURS` above zero for periodic polling. The service only records official-domain feed links as unverified admin review signals and never indexes feed content.

## Start the API

From the project root:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Or from this `backend` directory:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`. Health and interactive API documentation are at `/api/health` and `/docs`.

## API endpoints

- `GET /api/health`: reports backend and persisted vector-store availability.
- `GET /api/documents`: lists PDF files represented in Chroma metadata.
- `POST /api/chat`: accepts `{"query": "...", "conversation_id": "optional"}` and returns the model answer and actual retrieved source passages.

## Preserved RAG configuration

The existing pipeline and persisted Chroma collection are reused. The embedding model, 500-character chunks with 50-character overlap, retrieval configuration, Groq model and prompt, SQLite conversation memory, and explicit ingestion/query separation are unchanged. The existing vector database is at `vector_store/`; PDFs are at `data/pdfs/`; conversation history is at `data/conversations.sqlite3`.

API startup and user queries do not ingest PDFs or regenerate their embeddings. Ingestion remains an explicit operation, run only when intended:

```powershell
Set-Location backend
python -c "from src.rag_pipeline import RAGPipeline; print(RAGPipeline().ingest())"
```

## Tests

From the project root:

```powershell
python -m pytest backend\tests
```

Tests use the persisted local PDFs and vector store for path, loader, health, and document-list checks; model behavior in unit tests is isolated with fakes.
