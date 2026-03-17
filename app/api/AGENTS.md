<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# api

## Purpose
FastAPI 라우터 모듈. REST API 엔드포인트와 HTML 페이지 렌더링을 제공한다. HTMX 요청 시 HTML partial, 일반 요청 시 JSON을 반환하는 듀얼 응답 패턴을 사용한다.

## Key Files

| File | Description |
|------|-------------|
| `files.py` | `/api/files` — 파일 CRUD (목록/업로드/조회/수정/삭제/다운로드). HTMX 요청 시 `file_table.html` 또는 `file_row.html` partial 반환 |
| `parse.py` | `/api/files/{id}/parse*` — 파싱 시작(202), 상태 조회(JSON/HTML), 결과 ZIP 다운로드. `parser_client`가 `app.state`에서 주입됨 |
| `pages.py` | `/` (메인 페이지), `/api/partials/file-table` (HTMX partial). 검색/필터/페이지네이션 지원. 라우터 prefix 없음 |
| `__init__.py` | 빈 패키지 초기화 |

## For AI Agents

### Working In This Directory
- `files.py`와 `parse.py`는 모두 `prefix="/api/files"` 사용 — 경로 충돌 주의
- HTMX 감지: `request.headers.get("HX-Request")` 체크 후 `templates.TemplateResponse` 반환
- `parser_client` 접근: `getattr(request.app.state, "parser_client", None)` → None이면 503
- 페이지네이션: `page`, `page_size(per_page)` 파라미터, `total_pages` 계산
- 파일 다운로드: `FastAPIFileResponse`로 디스크 파일 스트리밍

### Common Patterns
- 업로드/삭제 후 HTMX 요청이면 전체 파일 테이블 partial 재렌더링
- 수정 후 HTMX 요청이면 해당 행만 `file_row.html`로 재렌더링
- `selectinload(FileModel.parse_jobs)` — 파일과 파싱 작업을 함께 로드

## Dependencies

### Internal
- `app/services/file_service.py` — 파일 비즈니스 로직
- `app/services/parse_service.py` — 파싱 비즈니스 로직
- `app/models/tables.py` — ORM 모델 (HTMX 렌더링용 쿼리)
- `app/templates/` — Jinja2 HTML 템플릿

### External
- `fastapi`, `sqlalchemy`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
