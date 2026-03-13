"""
Unit tests for background_sync logic.
Tests call _process_jobs_batch directly to avoid asyncio.sleep delays.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ParseJobStatus
from app.models.tables import File, ParseJob
from app.services.background_sync import _process_jobs_batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(**kwargs) -> File:
    defaults = dict(
        id=uuid.uuid4(),
        filename="test.pdf",
        stored_path=f"uploads/{uuid.uuid4()}.pdf",
        file_size=1024,
        mime_type="application/pdf",
        category="Uncategorized",
        uploader="Admin",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return File(**defaults)


def _make_job(file: File, status: str = ParseJobStatus.PROCESSING.value, **kwargs) -> ParseJob:
    defaults = dict(
        id=uuid.uuid4(),
        file_id=file.id,
        parser_job_id="test-parser-job-001",
        status=status,
        retry_failure_count=0,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return ParseJob(**defaults)


class _SessionCMFactory:
    """
    Replaces AsyncSessionLocal so _process_jobs_batch uses the test session.
    _process_jobs_batch does: `async with AsyncSessionLocal() as db:`
    so we need the instance to be callable and return an async CM.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def __call__(self):
        return _BorrowedSession(self._session)


class _BorrowedSession:
    """Async CM that yields the borrowed session without closing it."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            await self._session.commit()


# ---------------------------------------------------------------------------
# Fixtures: fresh session per test, cleaned up after
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sync_session(test_session_factory):
    """Session for background_sync unit tests with row cleanup."""
    async with test_session_factory() as session:
        yield session
        await session.execute(delete(ParseJob))
        await session.execute(delete(File))
        await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_updates_completed(sync_session: AsyncSession):
    """When parser returns completed, DB job status becomes completed."""
    file = _make_file()
    sync_session.add(file)
    job = _make_job(file, status=ParseJobStatus.PENDING.value)
    sync_session.add(job)
    await sync_session.commit()
    job_id = job.id  # capture before expiry

    mock_client = AsyncMock()
    mock_client.get_job_status = AsyncMock(
        return_value={"job_id": job.parser_job_id, "status": "completed"}
    )

    factory = _SessionCMFactory(sync_session)
    with patch("app.services.background_sync.AsyncSessionLocal", factory):
        await _process_jobs_batch(mock_client, [job])

    # Expire identity map so next select hits the DB
    sync_session.expunge_all()
    result = await sync_session.execute(select(ParseJob).where(ParseJob.id == job_id))
    updated = result.scalar_one()
    assert updated.status == ParseJobStatus.COMPLETED.value
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_sync_handles_failure(sync_session: AsyncSession):
    """Three consecutive sync failures → status=error."""
    file = _make_file()
    sync_session.add(file)
    job = _make_job(file, status=ParseJobStatus.PROCESSING.value, retry_failure_count=2)
    sync_session.add(job)
    await sync_session.commit()
    job_id = job.id

    mock_client = AsyncMock()
    mock_client.get_job_status = AsyncMock(side_effect=Exception("connection refused"))

    factory = _SessionCMFactory(sync_session)
    with patch("app.services.background_sync.AsyncSessionLocal", factory):
        await _process_jobs_batch(mock_client, [job])

    sync_session.expunge_all()
    result = await sync_session.execute(select(ParseJob).where(ParseJob.id == job_id))
    updated = result.scalar_one()
    assert updated.status == ParseJobStatus.ERROR.value
    assert updated.retry_failure_count >= 3


@pytest.mark.asyncio
async def test_sync_timeout(sync_session: AsyncSession):
    """Job older than 24h in processing state → status=timeout."""
    file = _make_file()
    sync_session.add(file)
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    job = _make_job(
        file,
        status=ParseJobStatus.PROCESSING.value,
        created_at=old_time,
    )
    sync_session.add(job)
    await sync_session.commit()
    job_id = job.id

    mock_client = AsyncMock()
    mock_client.get_job_status = AsyncMock(
        return_value={"job_id": job.parser_job_id, "status": "processing"}
    )

    factory = _SessionCMFactory(sync_session)
    with patch("app.services.background_sync.AsyncSessionLocal", factory):
        await _process_jobs_batch(mock_client, [job])

    sync_session.expunge_all()
    result = await sync_session.execute(select(ParseJob).where(ParseJob.id == job_id))
    updated = result.scalar_one()
    assert updated.status == ParseJobStatus.TIMEOUT.value


@pytest.mark.asyncio
async def test_resync_lost_jobs(sync_session: AsyncSession):
    """Parser returns 404 for job → status=lost."""
    import httpx

    file = _make_file()
    sync_session.add(file)
    job = _make_job(file, status=ParseJobStatus.PROCESSING.value)
    sync_session.add(job)
    await sync_session.commit()
    job_id = job.id

    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_client.get_job_status = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "404 Not Found", request=AsyncMock(), response=mock_response
        )
    )

    factory = _SessionCMFactory(sync_session)
    with patch("app.services.background_sync.AsyncSessionLocal", factory):
        await _process_jobs_batch(mock_client, [job])

    sync_session.expunge_all()
    result = await sync_session.execute(select(ParseJob).where(ParseJob.id == job_id))
    updated = result.scalar_one()
    assert updated.status == ParseJobStatus.LOST.value
