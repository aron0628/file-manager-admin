<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# alembic

## Purpose
SQLAlchemy ORM 모델 변경사항을 PostgreSQL에 반영하는 Alembic DB 마이그레이션 스크립트. autogenerate로 마이그레이션 생성, `upgrade head`로 적용.

## Key Files

| File | Description |
|------|-------------|
| `env.py` | Alembic 환경 설정 — async engine 연결, `target_metadata` 바인딩 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `versions/` | 자동 생성된 마이그레이션 리비전 파일들 |

## For AI Agents

### Working In This Directory
- 마이그레이션 생성: `make migrate msg="설명"` 또는 `uv run alembic revision --autogenerate -m "설명"`
- 마이그레이션 적용: `make upgrade` 또는 `uv run alembic upgrade head`
- 롤백: `make downgrade` 또는 `uv run alembic downgrade -1`
- ORM 모델(`app/models/tables.py`) 변경 후 반드시 마이그레이션 생성 필요

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
