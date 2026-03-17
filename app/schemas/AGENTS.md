<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# schemas

## Purpose
Pydantic v2 요청/응답 스키마. API 엔드포인트의 입출력 검증 및 직렬화를 담당한다.

## Key Files

| File | Description |
|------|-------------|
| `file.py` | `FileBase/Create/Update/Response` (파일 CRUD), `ParseJobResponse` (파싱 작업), `FileListResponse` (페이지네이션), `HealthResponse` |
| `__init__.py` | 빈 패키지 초기화 |

## For AI Agents

### Working In This Directory
- `model_config = {"from_attributes": True}` — ORM 모델에서 직접 변환 (`model_validate`)
- `Category`, `ParseJobStatus` 열거형은 `app/constants.py`에서 임포트
- `FileListResponse`는 페이지네이션 메타 포함 (total, page, page_size, total_pages)

## Dependencies

### Internal
- `app/constants.py` — `Category`, `ParseJobStatus` 열거형

### External
- `pydantic`

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
