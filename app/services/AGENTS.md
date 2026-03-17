<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# services

## Purpose
비즈니스 로직 레이어. 파일 관리, 파싱 연동, 백그라운드 상태 동기화를 담당한다. API 라우터에서 호출되며 ORM 모델을 직접 조작한다.

## Key Files

| File | Description |
|------|-------------|
| `file_service.py` | 파일 업로드(MIME 검증, 크기 제한, UUID 기반 저장), 목록(검색/카테고리/날짜 필터, 페이지네이션), 조회, 수정, 삭제(물리파일 + DB). path traversal 방어 포함 |
| `parse_service.py` | 파싱 시작(`parser_client.parse_pdf` → ParseJob 생성), 상태 조회(DB 캐시 반환, bg sync가 실제 동기화), 결과 다운로드(result_path 없으면 parser-server에서 자동 다운로드) |
| `background_sync.py` | 백그라운드 폴링 루프(`PARSE_POLL_INTERVAL_SECONDS` 간격). 미완료 job 배치 동기화, 세마포어 기반 동시성 제어. 상태 전이: completed, failed, error(3회 실패), timeout(24h), lost(404) |
| `__init__.py` | 빈 패키지 초기화 |

## For AI Agents

### Working In This Directory
- `file_service.py`: `_get_safe_stored_path`로 uploads/ 외부 경로 차단 (path traversal 방어)
- `parse_service.py`: 상태 조회는 DB 캐시만 반환 — 실시간 조회는 `background_sync`가 담당
- `background_sync.py`: `_process_jobs_batch`는 단독 `AsyncSessionLocal` 세션 사용 (요청 세션과 독립)
- completed 시 자동 다운로드: `parser_client.download_result` → `result_path` DB 저장

### Testing Requirements
- `file_service` 변경 시 `tests/test_file_api.py`에서 통합 테스트
- `parse_service` 변경 시 `tests/test_parse_api.py`에서 통합 테스트
- `background_sync` 변경 시 `tests/test_background_sync.py`에서 `_process_jobs_batch` 직접 호출 단위 테스트

### Common Patterns
- 서비스 함수는 `AsyncSession`을 첫 번째 인자로 받음 (의존성 주입)
- `parser_client`는 optional 파라미터 — None이면 503 반환
- `httpx.ConnectError`, `httpx.HTTPStatusError` 구분 처리

## Dependencies

### Internal
- `app/models/tables.py` — `File`, `ParseJob` ORM
- `app/config.py` — `settings`
- `app/constants.py` — 상태 열거형
- `app/database.py` — `AsyncSessionLocal` (background_sync에서 직접 사용)

### External
- `sqlalchemy`, `httpx`, `document-parser-client`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
