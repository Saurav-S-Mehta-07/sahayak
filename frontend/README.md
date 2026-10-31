# Yojana Sahayak frontend

Vite + React JavaScript frontend for the existing Python RAG backend. It does not contain model credentials or mock answers.

## Run locally

From the project root, configure the backend and install its dependencies:

```powershell
Copy-Item backend\.env.example backend\.env
# Set GROQ_API_KEY in backend\.env
python -m pip install -r backend\requirements.txt
```

Start the backend from the project root:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the local URL printed by Vite. `VITE_API_BASE_URL` defaults to `/api`, which the Vite development server proxies to port 8000. For a deployed backend, set it to the backend API origin ending in `/api`. The Python backend requires a valid `GROQ_API_KEY` in `backend/.env` for answer generation.

## Backend contract

- `GET /api/health`: API and Chroma readiness.
- `GET /api/documents`: PDF metadata represented in the existing Chroma collection.
- `POST /api/chat`: `{ "query": "...", "conversation_id": "..." }`, returning the answer, source passages, page metadata, and conversation ID.

Chat history is stored in browser `localStorage`; the returned conversation ID is also used by the backend's existing SQLite memory. The language selector is an interface preference only. The current RAG API has no response-language parameter, so it is not sent to the model.

## Production build

```powershell
npm run build
npm run preview
```
