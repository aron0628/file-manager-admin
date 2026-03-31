FROM python:3.13-slim

WORKDIR /app/file-manager-admin

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy editable dependency first so ../document-parser-client resolves correctly
COPY document-parser-client/ /app/document-parser-client/

# Copy lockfile and project metadata, then sync dependencies (without installing the project itself)
COPY file-manager-admin/pyproject.toml file-manager-admin/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and install the project
COPY file-manager-admin/ ./
RUN uv sync --frozen --no-dev

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD uv run python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
