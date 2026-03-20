from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tables import User
from app.services.auth_service import authenticate_user, create_user
from app.services.session_service import clear_session, create_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if user is not None:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if user is not None:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})


@router.post("/auth/login")
async def login(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, login_id, password)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "사용자 ID(또는 이메일) 또는 비밀번호가 올바르지 않습니다."},
            status_code=400,
        )
    response = RedirectResponse("/", status_code=302)
    create_session(response, user.user_id, user.session_version)
    return response


@router.post("/auth/signup")
async def signup(
    request: Request,
    user_id: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        await create_user(db, user_id, email, display_name, password)
    except ValueError as e:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": str(e)},
            status_code=400,
        )
    return RedirectResponse("/login", status_code=302)


@router.post("/auth/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    clear_session(response)
    return response
