"""
Integration tests for /api/files endpoints.
"""
import io
import shutil
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.conftest import make_pdf_bytes

# The service writes files relative to the process cwd (uploads/).
# We let that happen and clean up after tests via the autouse fixture below.

UPLOADS_DIR = Path("uploads")


@pytest.fixture(autouse=True)
def ensure_uploads_dir(tmp_path, monkeypatch):
    """Redirect file_service.UPLOADS_DIR to a per-test tmp subdir."""
    import app.services.file_service as fs

    test_uploads = tmp_path / "uploads"
    test_uploads.mkdir()
    monkeypatch.setattr(fs, "UPLOADS_DIR", test_uploads)
    yield
    # tmp_path is cleaned up automatically by pytest


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_pdf(authenticated_client: AsyncClient):
    """PDF upload returns 201 and stores UUID-based path."""
    pdf_bytes = make_pdf_bytes(512)
    response = await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"category": "Finance"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["category"] == "Finance"
    # stored_path should contain a UUID
    stored = data["stored_path"]
    parts = stored.replace("\\", "/").split("/")
    stem = Path(parts[-1]).stem
    uuid.UUID(stem)  # raises if not a valid UUID


@pytest.mark.asyncio
async def test_upload_invalid_mime(authenticated_client: AsyncClient):
    """Non-PDF upload returns 415."""
    response = await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"category": "Uncategorized"},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_oversized(authenticated_client: AsyncClient):
    """File exceeding MAX_UPLOAD_SIZE_MB returns 413."""
    import app.config as cfg

    original_max = cfg.settings.MAX_UPLOAD_SIZE_MB
    cfg.settings.MAX_UPLOAD_SIZE_MB = 0  # 0 MB → any content fails

    try:
        oversized = make_pdf_bytes(10)
        response = await authenticated_client.post(
            "/api/files/upload",
            files={"file": ("big.pdf", io.BytesIO(oversized), "application/pdf")},
            data={"category": "Uncategorized"},
        )
        assert response.status_code == 413
    finally:
        cfg.settings.MAX_UPLOAD_SIZE_MB = original_max


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_files(authenticated_client: AsyncClient):
    """Uploading a file then listing returns it."""
    await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("list_test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "HR"},
    )

    response = await authenticated_client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    filenames = [f["filename"] for f in data["items"]]
    assert "list_test.pdf" in filenames


@pytest.mark.asyncio
async def test_list_files_search(authenticated_client: AsyncClient):
    """Search filter returns matching files only."""
    await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("searchable_doc.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "Legal"},
    )

    response = await authenticated_client.get("/api/files?search=searchable_doc")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all("searchable_doc" in f["filename"] for f in data["items"])


@pytest.mark.asyncio
async def test_list_files_category(authenticated_client: AsyncClient):
    """Category filter returns only files with that category."""
    await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("cat_test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "Marketing"},
    )

    response = await authenticated_client.get("/api/files?category=Marketing")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(f["category"] == "Marketing" for f in data["items"])


# ---------------------------------------------------------------------------
# Get / Update / Delete / Download
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_file(authenticated_client: AsyncClient):
    """Single file retrieval by ID."""
    upload_resp = await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("get_test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "Admin"},
    )
    file_id = upload_resp.json()["id"]

    response = await authenticated_client.get(f"/api/files/{file_id}")
    assert response.status_code == 200
    assert response.json()["id"] == file_id


@pytest.mark.asyncio
async def test_update_file(authenticated_client: AsyncClient):
    """Updating filename and category persists correctly."""
    upload_resp = await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("update_test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "Uncategorized"},
    )
    file_id = upload_resp.json()["id"]

    response = await authenticated_client.put(
        f"/api/files/{file_id}",
        json={"filename": "renamed.pdf", "category": "Finance"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "renamed.pdf"
    assert data["category"] == "Finance"


@pytest.mark.asyncio
async def test_delete_file(authenticated_client: AsyncClient):
    """Deleted file returns 204 and subsequent GET returns 404."""
    upload_resp = await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("delete_test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")},
        data={"category": "Uncategorized"},
    )
    file_id = upload_resp.json()["id"]

    del_resp = await authenticated_client.delete(f"/api/files/{file_id}")
    assert del_resp.status_code == 204

    get_resp = await authenticated_client.get(f"/api/files/{file_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_download_file(authenticated_client: AsyncClient, tmp_path, monkeypatch):
    """Download endpoint returns the correct file bytes."""
    import app.services.file_service as fs
    import app.api.files as files_api

    # Use the same tmp uploads dir that ensure_uploads_dir already set,
    # but we need the download path resolution to match.
    # The service stores relative path like "uploads/<uuid>.pdf" in DB,
    # but the physical file is in tmp_path/uploads/<uuid>.pdf.
    # We patch the download handler's Path resolution by pointing UPLOADS_DIR
    # to the tmp dir and making the stored_path resolve correctly.

    pdf_bytes = make_pdf_bytes(256)
    upload_resp = await authenticated_client.post(
        "/api/files/upload",
        files={"file": ("download_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"category": "Uncategorized"},
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]
    stored_path = upload_resp.json()["stored_path"]

    # The physical file lives at tmp_path/uploads/<uuid>.pdf but
    # stored_path in DB is "uploads/<uuid>.pdf" (relative to cwd).
    # Manually copy it to make Path(stored_path).exists() return True.
    src = tmp_path / "uploads" / Path(stored_path).name
    dest = Path(stored_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

    try:
        dl_resp = await authenticated_client.get(f"/api/files/{file_id}/download")
        assert dl_resp.status_code == 200
        assert dl_resp.content == pdf_bytes
    finally:
        dest.unlink(missing_ok=True)
