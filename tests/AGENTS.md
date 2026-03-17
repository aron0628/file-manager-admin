<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# tests

## Purpose
pytest 기반 통합/단위 테스트. SQLite + aiosqlite로 PostgreSQL 없이 실행 가능. `conftest.py`에서 PostgreSQL UUID를 SQLite 호환 TypeDecorator로 패치한다.

## Key Files

| File | Description |
|------|-------------|
| `conftest.py` | 핵심 픽스처: SQLite UUID 패치, 테스트 엔진/세션, mock parser client, HTTP 클라이언트, `make_pdf_bytes` 헬퍼 |
| `test_file_api.py` | `/api/files` CRUD 엔드포인트 통합 테스트 — 업로드, 목록, 검색, 수정, 삭제, 다운로드 |
| `test_parse_api.py` | `/api/files/{id}/parse*` 엔드포인트 통합 테스트 — 파싱 시작, 상태 조회(JSON/HTMX), 결과 다운로드 |
| `test_background_sync.py` | `_process_jobs_batch` 단위 테스트 — completed/failure(3회→error)/timeout(24h)/lost 상태 전이 검증 |

## For AI Agents

### Working In This Directory
- 테스트 실행: `uv run pytest -v` (또는 `make test`)
- **UUID 패치 순서 중요**: `conftest.py`에서 `_SQLiteUUID` 패치가 앱 임포트보다 먼저 실행되어야 함
- `ensure_uploads_dir` autouse 픽스처가 `file_service.UPLOADS_DIR`을 `tmp_path`로 리다이렉트
- `mock_parser_client`는 `AsyncMock` 기반. `parse_pdf`, `get_job_status`, `download_result` 모킹됨
- `test_background_sync.py`는 `AsyncSessionLocal`을 패치하여 테스트 세션 주입 (`_SessionCMFactory`)

### Testing Requirements
- 새 API 엔드포인트 추가 시 `test_file_api.py` 또는 `test_parse_api.py`에 테스트 추가
- 백그라운드 동기화 로직 변경 시 `test_background_sync.py`에 상태 전이 테스트 추가
- `stored_path`가 디스크에 존재해야 하는 테스트는 `_make_stored_path_exist` 헬퍼 사용 후 `finally`에서 cleanup

### Common Patterns
- `httpx.AsyncClient` + `ASGITransport`로 FastAPI 앱 직접 호출 (실제 서버 불필요)
- 함수 스코프 세션 + 테스트 후 `delete(ParseJob)` → `delete(File)` 순서로 정리
- `monkeypatch.setattr`로 설정값/경로 오버라이드

## Dependencies

### Internal
- `app/` 전체 — 테스트 대상 앱 코드

### External
- `pytest`, `pytest-asyncio` — 테스트 프레임워크
- `httpx` — 비동기 HTTP 클라이언트 (ASGITransport)
- `aiosqlite` — SQLite 비동기 드라이버

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
