# File Manager Admin

PDF 파일 업로드 및 문서 파싱 관리자 UI.
외부 [document-parser-server](../document-parser-server)와 연동하여 PDF를 파싱하고 결과를 ZIP으로 다운로드합니다.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0 async, asyncpg |
| Frontend | Jinja2 SSR, HTMX 1.9.x, Tailwind CSS 3.x (CDN) |
| Database | PostgreSQL (production), SQLite (test) |
| Migration | Alembic |
| Package Manager | uv |
| External | document-parser-client (local editable package) |

## Quick Start

### 1. 의존성 설치

```bash
uv sync
```

> `document-parser-client`는 `../document-parser-client`에서 editable로 설치됩니다.

### 2. 환경변수 설정

```bash
cp .env.example .env  # 또는 직접 .env 생성
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_PORT` | `5432` | PostgreSQL 포트 |
| `DB_NAME` | `app_db` | 데이터베이스명 |
| `DB_USER` | `app_user` | 접속 계정 |
| `DB_PASSWORD` | `password` | 접속 비밀번호 |
| `UPLOAD_DIR` | `uploads` | 파일 업로드 저장 경로 |
| `PARSER_SERVER_URL` | `http://localhost:9997` | document-parser-server URL |
| `MAX_UPLOAD_SIZE_MB` | `100` | 최대 업로드 크기 (MB) |
| `ALLOWED_MIME_TYPES` | `["application/pdf"]` | 허용 MIME 타입 |
| `PARSE_RESULT_DIR` | `parse_results` | 파싱 결과 ZIP 저장 경로 |
| `PARSE_POLL_INTERVAL_SECONDS` | `10` | 백그라운드 동기화 간격 (초) |
| `PARSE_MAX_CONCURRENT_CHECKS` | `20` | 동기화 최대 동시 조회 수 |

### 3. DB 마이그레이션

```bash
make upgrade  # alembic upgrade head
```

### 4. 서버 실행

```bash
make dev  # uvicorn app.main:app --reload --port 8000
```

파싱 기능을 사용하려면 document-parser-server를 먼저 시작하세요:

```bash
# 터미널 1: parser server
cd ../document-parser-server
uv run uvicorn app.main:app --port 9997

# 터미널 2: admin server
make dev
```

> Parser server 없이도 앱은 정상 시작됩니다. 파싱 엔드포인트만 503을 반환합니다.

## Testing

```bash
make test  # uv run pytest -v
```

- SQLite + aiosqlite 사용 (PostgreSQL 불필요)
- `tests/conftest.py`에서 PostgreSQL UUID를 SQLite 호환 TypeDecorator로 패치

## Makefile

| Command | Description |
|---------|-------------|
| `make install` | 의존성 설치 (`uv sync`) |
| `make dev` | 개발 서버 실행 (--reload, :8000) |
| `make test` | 테스트 실행 (`uv run pytest -v`) |
| `make migrate msg="설명"` | Alembic 마이그레이션 생성 |
| `make upgrade` | 마이그레이션 적용 |
| `make downgrade` | 마이그레이션 롤백 |
| `make clean` | 캐시 및 임시 파일 정리 |

## Architecture

```
Browser (HTMX)
  ↕ HTML partial / JSON
FastAPI (:8000)
  ├── pages.py       → /                        메인 페이지
  │                   → /api/partials/file-table  HTMX 필터/페이지네이션
  ├── files.py       → /api/files                CRUD + 다운로드
  ├── parse.py       → /api/files/{id}/parse*    파싱 시작/상태/결과
  ├── services/
  │   ├── file_service.py       파일 관리 로직
  │   ├── parse_service.py      파싱 연동 로직
  │   └── background_sync.py    백그라운드 폴링 동기화
  └── AsyncDocumentParserClient
        ↕ HTTP
      document-parser-server (:9997)
```

### 주요 기능

- **파일 관리**: PDF 업로드 (드래그앤드롭), 목록 조회, 검색/필터, 수정, 삭제, 다운로드
- **문서 파싱**: parser-server에 PDF 전달 → 비동기 파싱 → 완료 시 결과 ZIP 자동 다운로드
- **실시간 UI**: HTMX 기반 partial 업데이트, 파싱 상태 3초 폴링, OOB swap
- **백그라운드 동기화**: 미완료 파싱 작업을 주기적으로 parser-server와 동기화

### Parse Job Lifecycle

```
pending → processing → completed (자동 ZIP 다운로드)
                     → failed
                     → error    (3회 연속 상태 조회 실패)
                     → timeout  (24시간 초과)
                     → lost     (parser-server에 job 없음)
```

## Project Structure

```
app/
  main.py               # FastAPI app + lifespan
  config.py             # pydantic-settings 환경변수
  database.py           # SQLAlchemy async engine, session
  constants.py          # Category, ParseJobStatus 열거형
  models/tables.py      # File, ParseJob ORM 모델
  schemas/file.py       # Pydantic 요청/응답 스키마
  api/
    files.py            # /api/files CRUD
    parse.py            # /api/files/{id}/parse* 파싱
    pages.py            # HTML 페이지 + HTMX partial
  services/
    file_service.py     # 파일 업로드/CRUD 로직
    parse_service.py    # 파싱 시작/상태/결과
    background_sync.py  # 백그라운드 폴링 동기화
  templates/
    base.html           # 레이아웃 (Tailwind, HTMX, 에러 토스트)
    index.html          # 메인 페이지
    components/         # 헤더, 필터 툴바
    partials/           # HTMX partial (테이블, 행, 모달, 상태 뱃지)
alembic/                # DB 마이그레이션
tests/                  # pytest 통합/단위 테스트
```

## License

Private
