"""Authentication tests: signup, login, logout."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    response = await client.post(
        "/auth/signup",
        data={
            "user_id": "newuser",
            "display_name": "New User",
            "email": "new@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    # First signup
    await client.post(
        "/auth/signup",
        data={
            "user_id": "user1",
            "display_name": "User 1",
            "email": "dup@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    # Duplicate
    response = await client.post(
        "/auth/signup",
        data={
            "user_id": "user2",
            "display_name": "User 2",
            "email": "dup@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "이미 등록된 이메일" in response.text


@pytest.mark.asyncio
async def test_signup_short_password(client: AsyncClient):
    response = await client.post(
        "/auth/signup",
        data={
            "user_id": "shortpw",
            "display_name": "Short PW",
            "email": "short@example.com",
            "password": "1234567",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "8자" in response.text


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    response = await client.post(
        "/auth/login",
        data={"login_id": "test@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


@pytest.mark.asyncio
async def test_login_success_with_user_id(client: AsyncClient, test_user):
    response = await client.post(
        "/auth/login",
        data={"login_id": "testuser", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    response = await client.post(
        "/auth/login",
        data={"login_id": "test@example.com", "password": "wrongpassword"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "올바르지 않습니다" in response.text


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        data={"login_id": "nobody@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_logout(authenticated_client: AsyncClient):
    response = await authenticated_client.post(
        "/auth/logout",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_login_page_renders(client: AsyncClient):
    response = await client.get("/login")
    assert response.status_code == 200
    assert "로그인" in response.text


@pytest.mark.asyncio
async def test_signup_page_renders(client: AsyncClient):
    response = await client.get("/signup")
    assert response.status_code == 200
    assert "회원가입" in response.text


@pytest.mark.asyncio
async def test_login_page_redirects_when_authenticated(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"
