<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# models

## Purpose
SQLAlchemy 2.0 async ORM 모델 정의. PostgreSQL 대상이며, 테스트 시 SQLite 호환 UUID 패치 적용.

## Key Files

| File | Description |
|------|-------------|
| `tables.py` | `File` (파일 메타데이터, UUID PK, 카테고리, 업로더) 및 `ParseJob` (파싱 작업 상태 추적, File FK, 재시도 카운터) ORM 모델 |
| `__init__.py` | 빈 패키지 초기화 |

## For AI Agents

### Working In This Directory
- `File` ↔ `ParseJob`: 1:N 관계, `cascade="all, delete-orphan"` (File 삭제 시 ParseJob도 삭제)
- `UUID(as_uuid=True)` 사용 — 테스트에서 `_SQLiteUUID` TypeDecorator로 패치됨
- `Mapped[]` 타입 힌트 + `mapped_column()` 패턴 (SQLAlchemy 2.0 선언적 매핑)
- 모델 변경 후 `make migrate msg="..."` 실행 필수

### Common Patterns
- PK: `uuid.uuid4()` 자동 생성
- `server_default=func.now()` — DB 레벨 기본값
- `onupdate=func.now()` — `updated_at` 자동 갱신
- `nullable=True` 필드: `error_message`, `result_path`, `completed_at`

## Dependencies

### Internal
- `app/database.py` — `Base` 선언적 베이스

### External
- `sqlalchemy` (core + dialects.postgresql)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
