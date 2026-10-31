# Yojana Sahayak

Yojana Sahayak combines a React/Vite frontend with the existing Python RAG backend. The existing RAG architecture and persisted vector store are reused.

## Project layout

- `frontend/`: React application and Vite configuration.
- `backend/app/`: FastAPI routes, request/response schemas, conversation orchestrator, and RAG service adapter.
- `backend/app/data/schemes.json`: source links for the scheme directory; entries do not imply that a PDF is indexed or verified.
- `backend/app/database.py`: additive account, session, conversation ownership, and document metadata tables in the existing SQLite database.
- `backend/src/`: the existing modular RAG pipeline and conversation memory.
- `backend/data/pdfs/`: source PDFs.
- `backend/vector_store/`: persisted Chroma database reused by API queries.
- `backend/tests/`: backend unit and API tests.

## Run locally

Configure the backend once:

```powershell
Copy-Item backend\.env.example backend\.env
# Set GROQ_API_KEY in backend\.env
python -m pip install -r backend\requirements.txt
```

Start the API from the project root:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The same backend can be started with the working directory set to `backend`:

```powershell
Set-Location backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Vite forwards `/api` requests to `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` in `frontend/.env` to `/api` for the development proxy or to a deployed backend API origin ending in `/api`.

## Accounts and administration

Citizen registration and login use HTTP-only, signed-random session cookies and CSRF tokens. New registrations always receive the citizen role. To create or promote an administrator, run this interactive command from the project root:

```powershell
python -m backend.app.services.admin_cli
```

Or, from `backend/`, run `python -m app.services.admin_cli`. Do not expose administrator credentials. Set `SESSION_COOKIE_SECURE=true` when the frontend and API are served over HTTPS. Configure `CORS_ORIGINS` with the exact frontend origins.

The public scheme directory lists portal links, not a claim that the corresponding PDF is available. Administrators upload PDFs, review the source, explicitly mark it verified, and then explicitly index it. Uploads are hash-deduplicated and stored separately under `backend/data/pdfs/managed/`; the existing PDFs and Chroma collection are not replaced.

## Official-feed discovery and review

Optional RSS/Atom discovery accepts comma-separated feed URLs in `SCHEME_DISCOVERY_FEEDS`. The backend only fetches HTTPS feeds on `.gov.in`/`.nic.in` hosts, rejects redirects, checks that the feed host resolves publicly, caps responses at 1 MB, and only records item links on those government domains. No feed is enabled by default because feed/API availability and terms vary by source. Configure only feeds whose use is permitted by that agency.

An administrator can run **Discover new schemes** in the administration page, or call `POST /api/admin/schemes/discover`. Set `SCHEME_DISCOVERY_INTERVAL_HOURS` to a positive value to enable periodic polling; `0` disables the scheduler. Discovery creates deduplicated, audited review signals only. Feed entries may be news or announcements, are not authoritative scheme guidelines, do not create or verify a scheme record, do not download PDFs, and are never indexed. Review outcomes and notes are recorded in SQLite. The current workflow does not yet convert a discovery signal into a new canonical scheme record; existing scheme records still use the existing source review, PDF upload, document verification, and explicit indexing path.

Not implemented by this discovery slice: extracted scheme profiles, generated summary PDFs, source-version comparison, outdated/discontinued scheme lifecycle, OCR, or background PDF/embedding jobs. No such completion is implied by an RSS discovery signal.

The notebook reads `GROQ_API_KEY` from the process environment instead of embedding a credential. The previously embedded key must be revoked/rotated with the provider; removing it from the working notebook does not invalidate copies or repository history.

## Current document inventory

The scheme catalog has 20 candidate scheme/source-portal records in `backend/app/data/schemes.json`; these are not 20 verified PDFs. At the time this documentation was updated, the persisted Chroma API inventory contained one indexed PDF, `Women Empowerment Schemes.pdf` (48 chunks across 5 pages), and the admin-managed document table contained no records. The PDF directory also contains `4d653-government-schemes-in-news.pdf`, a checkpoint copy under `backend/data/pdfs/.ipynb_checkpoints/`, and a hashed file under `backend/data/pdfs/managed/`; their presence alone does not establish verification or indexing. Do not treat the catalog count or these files as an official 20-document corpus.

## API

- `GET /api/health`: reports API and persisted vector-store availability.
- `GET /api/documents`: lists PDF metadata in the existing Chroma collection.
- `POST /api/chat`: requires an authenticated session and CSRF token; routes conversational turns separately from document questions and returns retrieved passages for RAG answers.
- `POST /api/eligibility/evaluate` and `/api/eligibility/recommendations`: authenticated, non-persistent profile checks against admin-entered criteria linked to verified/indexed PDF excerpts. Without such criteria the API reports insufficient evidence instead of guessing.
- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`: citizen sessions.
- `GET /api/schemes`: the 20-entry source directory.
- `GET /api/conversations`, `PATCH /api/conversations/{id}`, `DELETE /api/conversations/{id}`, and `DELETE /api/conversations/{id}/messages`: account-owned conversation history, rename, delete, and clear.
- `/api/admin/*`: administrator-only scheme document upload, verification, ingestion, and event history.

The frontend never receives backend credentials. The backend loads its environment from `backend/.env`; configure `CORS_ORIGINS` there for any deployed frontend origin. The frontend uses `/api` through the Vite development proxy by default. Configure `VITE_API_BASE_URL` only when connecting to a separately hosted API. SQLite and Chroma use local paths; production deployments must mount persistent storage for backend data and the vector store or conversation/document state will not survive ephemeral instance replacement.

## RAG pipeline and ingestion

The API reuses the existing persistent Chroma collection; it does not ingest PDFs or generate document embeddings at startup or for a user query. The embedding model, chunking settings, retrieval strategy, prompt, Groq model, and SQLite-backed conversation memory are preserved. Retrieved passage cards display indexed filenames, pages, excerpts, and scheme/source URL metadata only when attached; missing official URLs are called out rather than fabricated. Ingestion remains an explicit operation, for example:

```powershell
Set-Location backend
python -c "from src.rag_pipeline import RAGPipeline; print(RAGPipeline().ingest())"
```

Run this only when intentionally ingesting documents; it is not part of API startup.

The chat orchestrator avoids retrieval for recognized greetings, thanks, help, acknowledgments, and answer transformations. Conversation turns, response language, active scheme, and actual citation metadata are persisted per owned conversation. Script recognition and Romanized Hindi/Urdu classification are heuristic. For non-English factual questions, the configured LLM translates a concise retrieval query into English; the original question remains in the answer prompt, and the same existing Chroma index is queried. Hindi/Urdu and other language retrieval and answer quality have not been independently evaluated across all listed languages. This is not a certified 11-language NLP service, and an unavailable or irrelevant indexed source still requires abstention.

`POST /api/chat` accepts `auto`, English, Hindi, Urdu, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Hinglish, Roman Hindi, or Roman Urdu as `response_language`. Language detection is heuristic and answer quality has not been evaluated comprehensively for each language. Selection enables the existing model prompt and retrieval-normalization path; it is not a certification of language quality.

The chat language selector persists in the browser. The sidebar supports conversation search, rename, and delete; the chat toolbar can clear messages while retaining a conversation. `Ctrl+K` / `Command+K` starts a new conversation. In the message composer, `Enter` sends and `Shift+Enter` inserts a newline.

Voice is optional and uses browser-native Web Speech APIs. Microphone recognition and installed text-to-speech voices vary by browser, operating system, permissions, and locale. Unsupported recognition reports an error and leaves typed input available; if no matching speech voice is installed, the written answer remains available. No Bhashini or other hosted speech provider is configured, and the 11-language recognition/playback matrix has not been tested end-to-end.

Eligibility values submitted to the eligibility endpoints are evaluated in memory and are not saved as a user profile. Administrators may create criteria only against verified and indexed documents; the cited excerpt must occur on the selected PDF page. Criterion entry is a human-reviewed process, not automatic extraction. The results are preliminary and are not official eligibility decisions.

## Verify

```powershell
python -m pytest backend\tests
Set-Location frontend
npm run build
```

Backend dependencies and optional configuration are documented in [backend/README.md](backend/README.md). Frontend details are in [frontend/README.md](frontend/README.md).
