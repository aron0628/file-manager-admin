from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_auth
from app.models.tables import User
from app.services.auth_service import authenticate_user, create_user, hash_password
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


@router.post("/api/accounts", response_class=HTMLResponse)
async def create_account(
    request: Request,
    user_id: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(default="user"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        await create_user(db, user_id, email, display_name, password, role=role)
    except ValueError as e:
        return templates.TemplateResponse(
            "partials/account_create_form.html",
            {
                "request": request,
                "error": str(e),
                "form_data": {
                    "user_id": user_id,
                    "display_name": display_name,
                    "email": email,
                },
            },
            status_code=400,
        )

    # Success: return updated user table with pagination context
    page_size = 20
    total_result = await db.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    result = await db.execute(select(User).order_by(User.created_at.desc()).offset(0).limit(page_size))
    users = result.scalars().all()
    response = templates.TemplateResponse(
        "partials/account_user_table.html",
        {
            "request": request,
            "users": users,
            "total": total,
            "page": 1,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": 0,
            "search": "",
            "date_range": "",
        },
    )
    response.headers["HX-Trigger"] = "closeAccountModal"
    response.headers["HX-Retarget"] = "#account-user-table"
    response.headers["HX-Reswap"] = "outerHTML"
    return response


@router.put("/api/accounts/{user_id}", response_class=HTMLResponse)
async def update_account(
    request: Request,
    user_id: str,
    display_name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    is_active: str = Form(default="true"),
    password: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.user_id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="유효하지 않은 역할입니다.")

    # 자신의 역할/상태 변경 방지
    if user_id == current_user.user_id:
        if role != current_user.role:
            raise HTTPException(status_code=400, detail="자신의 역할은 변경할 수 없습니다.")
        if is_active == "false":
            raise HTTPException(status_code=400, detail="자신의 계정을 비활성화할 수 없습니다.")

    # 이메일 중복 검사 (자기 자신 제외)
    if email != target_user.email:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

    if password:
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="비밀번호는 최소 8자 이상이어야 합니다.")
        target_user.hashed_password = hash_password(password)

    target_user.display_name = display_name
    target_user.email = email
    target_user.role = role
    target_user.is_active = is_active == "true"
    await db.commit()
    await db.refresh(target_user)

    return templates.TemplateResponse(
        "partials/account_user_row.html",
        {"request": request, "u": target_user, "current_user": current_user},
    )


@router.post("/auth/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    clear_session(response)
    return response
