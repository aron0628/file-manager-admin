from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request
from fastapi.responses import Response

from app.config import settings
from app.services.settings_service import get_cached_int

SESSION_COOKIE_NAME = "session"

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def _session_max_age() -> int:
    """Return session max_age in seconds from DB-cached setting."""
    return get_cached_int("session_expire_hours") * 3600


def create_session(response: Response, user_id: str, session_version: int) -> None:
    token = _serializer.dumps({"uid": user_id, "sv": session_version})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=_session_max_age(),
        httponly=True,
        samesite="lax",
    )


def get_session_data(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=_session_max_age())
        return data
    except (BadSignature, SignatureExpired):
        return None


def clear_session(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME)
