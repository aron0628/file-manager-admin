# File Manager Admin

FastAPI-based admin UI for uploading PDF files and triggering document parsing via an external parser server.

## Tech Stack

- **Python 3.13** with `uv` package manager
- **FastAPI** — async REST API + Jinja2 HTML pages
- **SQLAlchemy 2.0 async** (`asyncpg` for PostgreSQL)
- **Alembic** — database migrations
- **HTMX** — frontend partial updates without JavaScript frameworks
- **document-parser-client** — local editable package at `../document-parser-client`

## Build & Run

```bash
# Install dependencies (including editable document-parser-client)
uv sync

# Start development server
uv run uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
# Run all tests (uses SQLite in-memory via aiosqlite — no PostgreSQL needed)
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_file_api.py -v
```

Tests use `sqlite+aiosqlite:///./test.db`. The `postgresql.UUID` column type is patched in `tests/conftest.py` with a `TypeDecorator` that stores UUIDs as `VARCHAR(36)`, making tests portable without PostgreSQL.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_PORT` | `5432` | PostgreSQL 포트 |
| `DB_NAME` | `app_db` | 데이터베이스명 |
| `DB_USER` | `app_user` | 접속 계정 |
| `DB_PASSWORD` | `password` | 접속 비밀번호 (특수문자 그대로 입력 가능) |
| `PARSER_SERVER_URL` | `http://localhost:9997` | Base URL of the document-parser-server |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload size in megabytes |
| `ALLOWED_MIME_TYPES` | `["application/pdf"]` | List of accepted MIME types |
| `PARSE_POLL_INTERVAL_SECONDS` | `10` | How often the background sync loop runs |
| `PARSE_MAX_CONCURRENT_CHECKS` | `20` | Max concurrent parser status checks per sync cycle |

Place overrides in a `.env` file at the project root. `pydantic-settings` loads it automatically.

## Project Structure

```
app/
  main.py               # FastAPI app + lifespan (parser client + background sync)
  config.py             # Settings via pydantic-settings
  database.py           # SQLAlchemy async engine, session, Base
  constants.py          # Category and ParseJobStatus enums
  models/
    tables.py           # ORM models: File, ParseJob
  schemas/
    file.py             # Pydantic request/response schemas
  api/
    files.py            # /api/files CRUD endpoints
    parse.py            # /api/files/{id}/parse* endpoints
    pages.py            # HTML page endpoints (HTMX)
  services/
    file_service.py     # File upload/list/update/delete logic
    parse_service.py    # Parse job start/status/result logic
    background_sync.py  # Periodic sync of parse job statuses
  templates/            # Jinja2 HTML templates
alembic/                # Database migration scripts
tests/
  conftest.py           # Fixtures: SQLite engine, DB session, mock parser client
  test_file_api.py      # File CRUD endpoint tests
  test_parse_api.py     # Parse endpoint tests
  test_background_sync.py  # Background sync unit tests
uploads/                # Uploaded files (UUID-named)
parse_results/          # Downloaded ZIP results from parser server
```

## document-parser-server Integration

On startup, the app connects to `PARSER_SERVER_URL` via `AsyncDocumentParserClient`. If the server is unavailable, the app starts anyway with `app.state.parser_client = None` and parse endpoints return `503`.

A background task polls active parse jobs every `PARSE_POLL_INTERVAL_SECONDS` seconds and updates their status in the DB. Job lifecycle:

```
pending → processing → completed
                     → failed
                     → error     (3 consecutive sync failures)
                     → timeout   (processing for > 24 hours)
                     → lost      (job not found on parser server)
```

To use parsing, start the document-parser-server first, then start this server:

```bash
# In ../document-parser-client directory
uv run uvicorn app.main:app --port 9997

# Then start this server
uv run uvicorn app.main:app --reload --port 8000
```
