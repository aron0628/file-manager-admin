<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# app

## Purpose
FastAPI 애플리케이션 코어. 앱 초기화(lifespan), 설정, DB 연결, ORM 모델, Pydantic 스키마, API 라우터, 비즈니스 로직 서비스, Jinja2 HTML 템플릿을 포함한다.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI 앱 생성, lifespan(파서 클라이언트 연결 + 백그라운드 동기화 태스크), 라우터 등록, `/health` 엔드포인트 |
| `config.py` | `pydantic-settings` 기반 `Settings` 클래스. `.env` 자동 로드. DB, 업로드, 파서 서버 설정 |
| `database.py` | SQLAlchemy async engine, `AsyncSessionLocal` 세션 팩토리, `Base` 선언적 베이스, `get_db` 의존성 |
| `constants.py` | `Category` (Finance, Marketing 등), `ParseJobStatus` (pending→completed/failed/error/timeout/lost) 열거형 |
| `__init__.py` | 빈 패키지 초기화 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `models/` | SQLAlchemy ORM 모델 (File, ParseJob) (see `models/AGENTS.md`) |
| `schemas/` | Pydantic 요청/응답 스키마 (see `schemas/AGENTS.md`) |
| `api/` | FastAPI 라우터 — REST API + HTML 페이지 (see `api/AGENTS.md`) |
| `services/` | 비즈니스 로직 — 파일 관리, 파싱 연동, 백그라운드 동기화 (see `services/AGENTS.md`) |
| `templates/` | Jinja2 HTML 템플릿 — 메인 페이지, 컴포넌트, HTMX partials (see `templates/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- `main.py`의 lifespan에서 `AsyncDocumentParserClient` 연결 실패 시에도 앱은 정상 시작 (parser_client=None)
- 모든 API 라우터는 `/api/files` prefix 사용 (pages.py 제외, `/` 루트)
- HTMX 요청(`HX-Request` 헤더)은 HTML partial 반환, 일반 요청은 JSON 반환하는 듀얼 응답 패턴
- DB 세션은 `get_db` 의존성 주입으로 관리

### Common Patterns
- 서비스 레이어 분리: API 라우터 → 서비스 함수 → ORM 모델
- `selectinload`로 N+1 쿼리 방지 (File → ParseJob 관계)
- UUID 기반 파일 저장 경로 (path traversal 방지)
- `parser_client`는 `app.state`에 저장, 없으면 파싱 엔드포인트 503 반환

## Dependencies

### Internal
- `document-parser-client` (`../document-parser-client`) — `AsyncDocumentParserClient`

### External
- `fastapi`, `sqlalchemy`, `jinja2`, `httpx`, `pydantic-settings`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
