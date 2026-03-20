from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request
from fastapi.responses import Response

from app.config import settings

SESSION_COOKIE_NAME = "session"

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def create_session(response: Response, user_id: str, session_version: int) -> None:
    token = _serializer.dumps({"uid": user_id, "sv": session_version})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
    )


def get_session_data(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=settings.SESSION_EXPIRE_HOURS * 3600)
        return data
    except (BadSignature, SignatureExpired):
        return None


def clear_session(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME)
