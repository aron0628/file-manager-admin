"""
Integration tests for /api/files/{file_id}/parse* endpoints.
"""
import io
import shutil
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.conftest import make_pdf_bytes


@pytest.fixture(autouse=True)
def ensure_uploads_dir(tmp_path, monkeypatch):
    """Redirect file_service.UPLOADS_DIR to a per-test tmp subdir."""
    import app.services.file_service as fs

    test_uploads = tmp_path / "uploads"
    test_uploads.mkdir()
    monkeypatch.setattr(fs, "UPLOADS_DIR", test_uploads)
    yield


async def _upload_pdf(authenticated_client: AsyncClient, filename: str = "parse_test.pdf") -> dict:
    """Upload a PDF and return the full response JSON."""
    resp = await authenticated_client.post(
        "/api/files/upload",
        files={"file": (filename, io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "Uncategorized"},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()


def _make_stored_path_exist(file_data: dict, tmp_path: Path) -> Path:
    """
    The DB stores stored_path as 'uploads/<uuid>.pdf' (relative).
    parse_service checks Path(stored_path).exists() before calling the parser.
    Copy the file from tmp_path/uploads/ to the relative path so the check passes.
    """
    stored_path = Path(file_data["stored_path"])
    src = tmp_path / "uploads" / stored_path.name
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, stored_path)
    return stored_path


# ---------------------------------------------------------------------------
# start parse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_parse(authenticated_client: AsyncClient, tmp_path, mock_parser_client):
    """POST /{file_id}/parse calls parser_client.parse_pdf and returns 202."""
    file_data = await _upload_pdf(authenticated_client)
    stored = _make_stored_path_exist(file_data, tmp_path)

    try:
        response = await authenticated_client.post(f"/api/files/{file_data['id']}/parse")
        assert response.status_code == 202
        data = response.json()
        assert data["parser_job_id"] == "test-job-123"
        assert data["status"] == "pending"
        mock_parser_client.parse_pdf.assert_called_once()
    finally:
        stored.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_start_parse_no_server(authenticated_client: AsyncClient, tmp_path):
    """POST /{file_id}/parse when parser_client is None returns 503."""
    file_data = await _upload_pdf(authenticated_client)
    stored = _make_stored_path_exist(file_data, tmp_path)

    from app.main import app as the_app
    the_app.state.parser_client = None

    try:
        response = await authenticated_client.post(f"/api/files/{file_data['id']}/parse")
        assert response.status_code == 503
    finally:
        stored.unlink(missing_ok=True)
        # Restore mock_parser_client — client fixture will restore on teardown
        # but we need it for the rest of this test run.  The fixture scope is
        # function so the next test gets a fresh client with mock restored.


# ---------------------------------------------------------------------------
# parse status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_status(authenticated_client: AsyncClient, tmp_path):
    """GET /{file_id}/parse-status returns DB-cached status as JSON."""
    file_data = await _upload_pdf(authenticated_client)
    stored = _make_stored_path_exist(file_data, tmp_path)

    try:
        parse_resp = await authenticated_client.post(f"/api/files/{file_data['id']}/parse")
        assert parse_resp.status_code == 202

        status_resp = await authenticated_client.get(f"/api/files/{file_data['id']}/parse-status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["file_id"] == file_data["id"]
        assert data["parser_job_id"] == "test-job-123"
        assert "status" in data
    finally:
        stored.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_parse_status_htmx(authenticated_client: AsyncClient, tmp_path):
    """GET /{file_id}/parse-status with HX-Request header returns HTML partial."""
    file_data = await _upload_pdf(authenticated_client)
    stored = _make_stored_path_exist(file_data, tmp_path)

    try:
        await authenticated_client.post(f"/api/files/{file_data['id']}/parse")

        status_resp = await authenticated_client.get(
            f"/api/files/{file_data['id']}/parse-status",
            headers={"HX-Request": "true"},
        )
        assert status_resp.status_code == 200
        content_type = status_resp.headers.get("content-type", "")
        assert "text/html" in content_type
    finally:
        stored.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_parse_status_no_job(authenticated_client: AsyncClient):
    """GET /{file_id}/parse-status without any parse job returns 404."""
    file_data = await _upload_pdf(authenticated_client)
    status_resp = await authenticated_client.get(f"/api/files/{file_data['id']}/parse-status")
    assert status_resp.status_code == 404


# ---------------------------------------------------------------------------
# parse result - not ready
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_result_not_ready(authenticated_client: AsyncClient, tmp_path):
    """GET /{file_id}/parse-result when job is pending returns 409."""
    file_data = await _upload_pdf(authenticated_client)
    stored = _make_stored_path_exist(file_data, tmp_path)

    try:
        await authenticated_client.post(f"/api/files/{file_data['id']}/parse")
        result_resp = await authenticated_client.get(f"/api/files/{file_data['id']}/parse-result")
        assert result_resp.status_code == 409
    finally:
        stored.unlink(missing_ok=True)
