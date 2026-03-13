.PHONY: install dev test lint migrate upgrade downgrade clean

# 의존성 설치
install:
	uv sync

# 개발 서버 실행
dev:
	uv run uvicorn app.main:app --reload --port 8000

# 테스트 실행
test:
	uv run pytest -v

# Alembic 마이그레이션 생성
migrate:
	uv run alembic revision --autogenerate -m "$(msg)"

# Alembic 마이그레이션 적용
upgrade:
	uv run alembic upgrade head

# Alembic 마이그레이션 롤백
downgrade:
	uv run alembic downgrade -1

# 캐시 및 임시 파일 정리
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f test.db
