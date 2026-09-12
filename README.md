# Agent MCP — Gmail + Google Drive

A LangGraph/FastAPI agent that searches Gmail by sender and Google Drive
by file name, with the Google tools exposed over MCP.

```
frontend (React + Vite)  ->  backend (FastAPI)  ->  MCP stdio server  ->  Google APIs
```

## Layout

| Path | Purpose |
|---|---|
| `backend/agent.py` | FastAPI app, query routing, LangGraph wiring |
| `backend/mcp_server.py` | MCP server exposing `search_gmail` and `search_google_drive` |
| `backend/auth.py` | One-time Google OAuth consent |
| `frontend/` | React + Vite UI |

## Setup

### 1. Google OAuth client

Create a **Desktop app** OAuth client in the Google Cloud console, enable the
Gmail API and Drive API, then download the JSON as `backend/credentials.json`.
See `backend/credentials.json.example` for the expected shape.

Scopes used (both read-only):

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/drive.readonly`

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt

cp .env.example .env          # add your OPENAI_API_KEY

venv\Scripts\python.exe auth.py     # one time, opens a browser
venv\Scripts\python.exe agent.py    # serves on http://localhost:8000
```

`auth.py` writes `backend/token.json`. Pick the Google account whose mail and
files you actually want to search — the account picker matters, and searching
the wrong account looks exactly like "no results".

To switch accounts later, delete `token.json` and re-run `auth.py`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

## API

`POST /query`

```json
{ "query": "search drive for resume" }
```

```json
{ "answer": "Found 1 file(s) in Google Drive: ..." }
```

`answer` is always a string, including for errors and rejections, and may
contain newlines — render with `white-space: pre-wrap`.

`GET /` is a health check. `GET /docs` is the Swagger UI.

## Query forms

Gmail is searched **by sender only** — not subject or body.

```
emails from someone@example.com
show me emails from mohd
search gmail for mohd
```

Drive is searched **by file name**.

```
search drive for resume
find file named BoardingPass.pdf in drive
google drive resume
```

Anything else returns a message listing these forms. Unrecognized queries are
logged server-side so they can be diagnosed.

## Secrets

`.env`, `credentials.json`, and `token.json` are gitignored and must never be
committed. `token.json` in particular grants read access to a real Gmail and
Drive account.
