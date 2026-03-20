"""
Test configuration and fixtures.

Uses SQLite + aiosqlite for in-process async DB without requiring PostgreSQL.

The ORM models use sqlalchemy.dialects.postgresql.UUID(as_uuid=True) which
passes raw uuid.UUID objects to SQLite — unsupported.  We solve this by
monkeypatching postgresql.UUID with a TypeDecorator that stores UUIDs as
VARCHAR(36) strings, compatible with SQLite and PostgreSQL alike.

Transaction strategy: each test gets its own session; rows are deleted after
each test (truncate-style).  We cannot use SAVEPOINT rollback because the
production service code calls session.commit() which closes the enclosing
transaction context.
"""
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy import types as sa_types
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# UUID TypeDecorator — SQLite-compatible, must be patched BEFORE app imports
# ---------------------------------------------------------------------------

class _SQLiteUUID(sa_types.TypeDecorator):
    """Stores UUID as VARCHAR(36); works on both SQLite and PostgreSQL."""

    impl = sa_types.String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


# Patch BEFORE any app code is imported.
import sqlalchemy.dialects.postgresql as _pg_dialect  # noqa: E402
import sqlalchemy.dialects.postgresql.base as _pg_base  # noqa: E402

_pg_dialect.UUID = _SQLiteUUID  # type: ignore[attr-defined]
_pg_base.UUID = _SQLiteUUID  # type: ignore[attr-defined]

# App imports (use patched UUID)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.tables import File, ParseJob, User  # noqa: E402

# ---------------------------------------------------------------------------
# Engine / session factory (session-scoped to avoid recreating tables)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped session.  After the test, delete all rows so each test
    starts with a clean slate.  We don't wrap in begin() because the
    production code calls commit() which would break a nested context.
    """
    async with test_session_factory() as session:
        yield session
        # Cleanup: delete in FK-safe order (children first)
        await session.execute(delete(ParseJob))
        await session.execute(delete(File))
        await session.execute(delete(User))
        await session.commit()


# ---------------------------------------------------------------------------
# Mock parser client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_parser_client():
    client = AsyncMock()
    client.parse_pdf = AsyncMock(return_value={"job_id": "test-job-123", "status": "pending"})
    client.get_job_status = AsyncMock(return_value={"job_id": "test-job-123", "status": "completed"})
    client.download_result = AsyncMock(return_value=("parse_results/test-job-123.zip", {}))
    return client


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session, mock_parser_client) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.parser_client = mock_parser_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    app.state.parser_client = None


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user for authentication tests."""
    from app.services.auth_service import hash_password
    user = User(
        user_id="testuser",
        display_name="Test User",
        email="test@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def authenticated_client(db_session, mock_parser_client, test_user) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with session cookie set for the test user."""
    from app.database import get_db
    from app.main import app
    from app.services.session_service import SESSION_COOKIE_NAME
    from itsdangerous import URLSafeTimedSerializer
    from app.config import settings

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.parser_client = mock_parser_client

    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    token = serializer.dumps({"uid": test_user.user_id, "sv": test_user.session_version})

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={SESSION_COOKIE_NAME: token},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    app.state.parser_client = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pdf_bytes(size: int = 1024) -> bytes:
    header = b"%PDF-1.4\n"
    return header + b"x" * max(0, size - len(header))
