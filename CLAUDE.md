# File Manager Admin

PDF 파일 업로드 및 문서 파싱 관리자 UI. 외부 document-parser-server와 연동하여 PDF 파싱 후 결과를 다운로드한다.

## Tech Stack

- **Python 3.13** with `uv` package manager
- **FastAPI** — async REST API + Jinja2 HTML pages
- **SQLAlchemy 2.0 async** (`asyncpg` for PostgreSQL)
- **Alembic** — database migrations
- **HTMX 1.9.x** + **Tailwind CSS 3.x** (CDN) — SPA 없이 서버 사이드 렌더링 기반 동적 UI
- **document-parser-client** — local editable package at `../document-parser-client`

## Build & Run

```bash
# Install dependencies (including editable document-parser-client)
uv sync

# Start development server
uv run uvicorn app.main:app --reload --port 8000

# Or use Makefile
make install  # uv sync
make dev      # uvicorn --reload --port 8000
```

## Testing

```bash
# Run all tests (uses SQLite via aiosqlite — no PostgreSQL needed)
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_file_api.py -v

# Or use Makefile
make test
```

- Tests use `sqlite+aiosqlite:///./test.db` (file-based, not in-memory)
- `postgresql.UUID` is patched in `tests/conftest.py` with `_SQLiteUUID` TypeDecorator (VARCHAR(36))
- **UUID 패치 순서 중요**: 패치가 앱 임포트보다 먼저 실행되어야 함
- 각 테스트는 함수 스코프 세션 사용, 테스트 후 ParseJob → File 순서로 truncate
- `ensure_uploads_dir` autouse 픽스처가 `UPLOADS_DIR`을 `tmp_path`로 리다이렉트
- `mock_parser_client`는 `AsyncMock` 기반 (`parse_pdf`, `get_job_status`, `download_result`)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_PORT` | `5432` | PostgreSQL 포트 |
| `DB_NAME` | `app_db` | 데이터베이스명 |
| `DB_USER` | `app_user` | 접속 계정 |
| `DB_PASSWORD` | `password` | 접속 비밀번호 (특수문자 그대로 입력 가능) |
| `UPLOAD_DIR` | `uploads` | 파일 업로드 저장 경로 |
| `PARSER_SERVER_URL` | `http://localhost:9997` | document-parser-server Base URL |
| `MAX_UPLOAD_SIZE_MB` | `100` | 최대 업로드 크기 (MB) |
| `ALLOWED_MIME_TYPES` | `["application/pdf"]` | 허용 MIME 타입 |
| `PARSE_RESULT_DIR` | `parse_results` | 파싱 결과 ZIP 다운로드 경로 |
| `PARSE_POLL_INTERVAL_SECONDS` | `10` | 백그라운드 동기화 폴링 간격 (초) |
| `PARSE_MAX_CONCURRENT_CHECKS` | `20` | 동기화 사이클당 최대 동시 상태 조회 수 |

Place overrides in a `.env` file at the project root. `pydantic-settings` loads it automatically.

## Architecture

```
Browser (HTMX)
  ↕ HTML partial / JSON (dual response)
FastAPI (:8000)
  ├── pages.py      → GET /           Jinja2 메인 페이지
  │                  → GET /api/partials/file-table  HTMX 필터/페이지네이션
  ├── files.py      → /api/files      CRUD + 다운로드
  ├── parse.py      → /api/files/{id}/parse*  파싱 시작/상태/결과
  ├── services/
  │   ├── file_service.py      파일 업로드/조회/수정/삭제
  │   ├── parse_service.py     파싱 시작/상태/결과 다운로드
  │   └── background_sync.py   백그라운드 폴링 동기화
  └── AsyncDocumentParserClient (app.state)
        ↕ HTTP
      document-parser-server (:9997)
```

### Key Patterns

- **듀얼 응답**: `HX-Request` 헤더 감지 → HTML partial 반환, 없으면 JSON 반환
- **서비스 레이어 분리**: API 라우터 → 서비스 함수 → ORM 모델
- **N+1 방지**: `selectinload(File.parse_jobs)` 사용
- **UUID 파일 저장**: 업로드 파일은 `uploads/{uuid}.pdf`로 저장 (path traversal 방어: `_get_safe_stored_path`)
- **parser_client 주입**: `app.state.parser_client` — None이면 파싱 엔드포인트 503
- **HTMX OOB swap**: 파싱 완료 시 다운로드 버튼 자동 표시 (`hx-swap-oob="true"`)
- **HTMX 폴링**: `parse_status.html`이 3초마다 자동 갱신 (`hx-trigger="every 3s"`)

## Project Structure

```
app/
  main.py               # FastAPI app + lifespan (parser client 연결 + background sync)
  config.py             # pydantic-settings 기반 Settings
  database.py           # SQLAlchemy async engine, AsyncSessionLocal, Base, get_db
  constants.py          # Category (Finance/Marketing/Admin/Legal/HR/Uncategorized)
                        # ParseJobStatus (pending/processing/completed/failed/error/timeout/lost)
  models/
    tables.py           # File (UUID PK, 1:N ParseJob cascade), ParseJob (상태 추적, retry 카운터)
  schemas/
    file.py             # FileBase/Create/Update/Response, ParseJobResponse, FileListResponse, HealthResponse
  api/
    files.py            # /api/files — CRUD + 다운로드 + HTMX partial 반환
    parse.py            # /api/files/{id}/parse — 파싱 시작(202)/상태/결과 ZIP 다운로드
    pages.py            # / (메인), /api/partials/file-table (HTMX partial)
  services/
    file_service.py     # 업로드(MIME/크기 검증), 목록(검색/카테고리/날짜 필터), CRUD
    parse_service.py    # 파싱 시작 → ParseJob 생성, 상태 조회(DB 캐시), 결과 다운로드
    background_sync.py  # 폴링 루프 + _process_jobs_batch (세마포어 동시성, 자동 ZIP 다운로드)
  templates/
    base.html           # 레이아웃: Tailwind CDN, HTMX CDN, 글로벌 로딩/에러 토스트
    index.html          # 메인 페이지: header + filter_toolbar + file_table
    components/
      header.html       # 페이지 헤더 + 업로드 버튼
      filter_toolbar.html  # 검색, 파일 타입, 날짜 범위 필터 (HTMX 실시간 필터링)
    partials/
      file_table.html   # 파일 목록 테이블 (업로드/삭제/필터 후 교체)
      file_row.html     # 단일 파일 행 (수정 후 행 단위 교체)
      pagination.html   # 페이지네이션 (HTMX 페이지 전환)
      parse_status.html # 파싱 상태 뱃지 (3초 폴링, OOB 다운로드 버튼)
      upload_modal.html # 업로드 모달 (드래그앤드롭)
      edit_modal.html   # 편집 모달
      empty_state.html  # 파일 없음 상태
alembic/                # DB 마이그레이션 (make migrate/upgrade/downgrade)
tests/
  conftest.py           # SQLite UUID 패치, 테스트 엔진/세션, mock parser client, make_pdf_bytes
  test_file_api.py      # 파일 CRUD 통합 테스트 (업로드/목록/검색/수정/삭제/다운로드)
  test_parse_api.py     # 파싱 통합 테스트 (시작/상태 JSON·HTMX/결과 미완료)
  test_background_sync.py  # 백그라운드 동기화 단위 테스트 (completed/error/timeout/lost)
uploads/                # UUID 기반 업로드 파일 (git-ignored)
parse_results/          # 파싱 결과 ZIP (git-ignored)
```

## document-parser-server Integration

앱 시작 시 `PARSER_SERVER_URL`로 `AsyncDocumentParserClient` 연결. 서버 불가 시에도 앱은 정상 시작 (`parser_client=None`, 파싱 503).

### Parse Job Lifecycle

```
pending → processing → completed → (자동 ZIP 다운로드 → result_path DB 저장)
                     → failed
                     → error     (3회 연속 상태 조회 실패)
                     → timeout   (24시간 초과 processing)
                     → lost      (parser-server에 job 없음)
```

### Background Sync

- `PARSE_POLL_INTERVAL_SECONDS` 간격으로 미완료 job(pending/processing) 배치 동기화
- `asyncio.Semaphore(PARSE_MAX_CONCURRENT_CHECKS)` 동시성 제어
- completed 시 `parser_client.download_result` → `parse_results/` 자동 다운로드
- 서버 재시작 시 `resync_pending_jobs`로 미완료 작업 즉시 재동기화

### Running with Parser Server

```bash
# 1. document-parser-server 시작 (별도 프로젝트)
cd ../document-parser-server
uv run uvicorn app.main:app --port 9997

# 2. 이 서버 시작
cd ../file-manager-admin
make dev
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | `uv sync` — 의존성 설치 |
| `make dev` | 개발 서버 실행 (--reload, :8000) |
| `make test` | `uv run pytest -v` |
| `make migrate msg="..."` | Alembic 마이그레이션 생성 |
| `make upgrade` | 마이그레이션 적용 |
| `make downgrade` | 마이그레이션 롤백 |
| `make clean` | `__pycache__`, `*.pyc`, `test.db` 정리 |
