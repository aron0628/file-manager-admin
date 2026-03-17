<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# File Manager Admin

## Purpose
FastAPI 기반 PDF 파일 업로드 및 문서 파싱 관리자 UI. 외부 document-parser-server와 연동하여 PDF를 파싱하고 결과를 다운로드한다. 프론트엔드는 HTMX + Tailwind CSS로 SPA 없이 서버 사이드 렌더링 기반 인터랙션을 제공한다.

## Key Files

| File | Description |
|------|-------------|
| `pyproject.toml` | 프로젝트 메타데이터, 의존성, pytest/hatch 설정 |
| `Makefile` | install, dev, test, migrate, clean 등 편의 명령어 |
| `alembic.ini` | Alembic DB 마이그레이션 설정 |
| `CLAUDE.md` | AI 에이전트용 프로젝트 컨텍스트 문서 |
| `.env` | 환경변수 오버라이드 (pydantic-settings 자동 로드) |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `app/` | 애플리케이션 소스 코드 — FastAPI 앱, ORM, 서비스, 템플릿 (see `app/AGENTS.md`) |
| `alembic/` | Alembic DB 마이그레이션 스크립트 (see `alembic/AGENTS.md`) |
| `tests/` | pytest 기반 통합/단위 테스트 (see `tests/AGENTS.md`) |
| `uploads/` | 업로드된 PDF 파일 저장소 (UUID 기반 파일명, git-ignored) |
| `parse_results/` | 파싱 완료 후 다운로드된 ZIP 결과 파일 (git-ignored) |

## For AI Agents

### Working In This Directory
- `uv`로 의존성 관리. `uv sync` 후 `uv run`으로 실행
- `document-parser-client`는 `../document-parser-client`에 위치한 로컬 editable 패키지
- `.env` 파일로 환경변수 오버라이드. DB 접속정보, 파서 서버 URL 등 포함
- 한글 UI/로그 사용 중. 코드 주석 및 사용자 메시지 한글

### Testing Requirements
- `uv run pytest -v`로 전체 테스트 실행
- SQLite + aiosqlite 사용 (PostgreSQL 불필요). `tests/conftest.py`에서 UUID TypeDecorator 패치
- 테스트 DB: `./test.db` (세션 스코프로 생성, 테스트 후 truncate)

### Architecture Overview
```
Client (Browser)
  ↕ HTMX partial requests
FastAPI (app/main.py)
  ├── pages.py → Jinja2 HTML 렌더링
  ├── files.py → /api/files CRUD + 파일 다운로드
  ├── parse.py → /api/files/{id}/parse* 파싱 연동
  ├── services/
  │   ├── file_service.py → 파일 업로드/조회/수정/삭제
  │   ├── parse_service.py → 파싱 시작/상태/결과 다운로드
  │   └── background_sync.py → 백그라운드 폴링 동기화
  └── document-parser-client (외부 패키지)
        ↕ HTTP
      document-parser-server (:9997)
```

### Parse Job Lifecycle
```
pending → processing → completed → (auto-download ZIP)
                     → failed
                     → error     (3회 연속 상태 조회 실패)
                     → timeout   (24시간 초과 processing)
                     → lost      (parser-server에 job 없음)
```

## Dependencies

### External
- `fastapi` + `uvicorn` — 비동기 웹 프레임워크
- `sqlalchemy[asyncio]` + `asyncpg` — 비동기 ORM (PostgreSQL)
- `alembic` — DB 마이그레이션
- `jinja2` — 서버 사이드 템플릿
- `htmx` 1.9.x — 프론트엔드 인터랙션 (CDN)
- `tailwindcss` 3.x — CSS 프레임워크 (CDN)
- `httpx` — HTTP 클라이언트
- `pydantic-settings` — 환경변수 관리
- `document-parser-client` — 로컬 editable 파서 클라이언트 패키지

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
