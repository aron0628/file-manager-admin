# NOTE: Register the exception handler in app/main.py:
# from app.dependencies import _AuthRedirectException
# @app.exception_handler(_AuthRedirectException)
# async def auth_redirect_handler(request, exc):
#     return exc.response

from fastapi import Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import User
from app.services.session_service import get_session_data


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    session_data = get_session_data(request)
    if not session_data:
        return None

    user_id = session_data.get("uid")
    session_version = session_data.get("sv")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not user.is_active:
        return None
    if user.session_version != session_version:
        return None

    return user


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_current_user(request, db)
    if user is None:
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            response = Response(status_code=200)
            response.headers["HX-Redirect"] = "/login"
            raise _AuthRedirectException(response)
        else:
            from fastapi.responses import RedirectResponse
            raise _AuthRedirectException(RedirectResponse("/login", status_code=302))

    request.state.user = user
    return user


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await require_auth(request, db)
    if user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user


class _AuthRedirectException(Exception):
    def __init__(self, response: Response):
        self.response = response
