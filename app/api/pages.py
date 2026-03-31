from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import UserRole
from app.database import get_db
from app.dependencies import require_admin, require_auth
from app.models.tables import File, User
from app.services.settings_service import get_cached_int

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _build_file_query(
    search: Optional[str],
    file_type: Optional[str],
    date_range: Optional[str],
    current_user_id: Optional[str] = None,
    current_user_role: Optional[str] = None,
):
    """Build SQLAlchemy WHERE conditions from filter params."""
    conditions = []

    # 소유권 필터: admin이 아니면 본인 파일만
    if current_user_role != UserRole.ADMIN.value and current_user_id:
        conditions.append(File.owner_id == current_user_id)

    if search:
        conditions.append(File.filename.ilike(f"%{search}%"))

    if file_type == "pdf":
        conditions.append(File.mime_type == "application/pdf")

    if date_range:
        try:
            days = int(date_range)
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            conditions.append(File.created_at >= cutoff)
        except ValueError:
            pass

    return conditions


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    search: Optional[str] = Query(default=None),
    file_type: Optional[str] = Query(default=None),
    date_range: Optional[str] = Query(default="30"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    conditions = _build_file_query(search, file_type, date_range, current_user_id=user.user_id, current_user_role=user.role)

    count_stmt = select(File)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))

    total_result = await db.execute(count_stmt)
    all_files = total_result.scalars().all()
    total = len(all_files)

    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    stmt = select(File).options(selectinload(File.parse_jobs)).order_by(File.created_at.desc()).offset(offset).limit(page_size)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    files = result.scalars().all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "files": files,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": offset,
            "search": search or "",
            "file_type": file_type or "",
            "date_range": date_range or "",
            "max_upload_size_mb": get_cached_int("max_upload_size_mb"),
            "active_nav": "files",
        },
    )


@router.get("/api/partials/file-table", response_class=HTMLResponse)
async def file_table_partial(
    request: Request,
    search: Optional[str] = Query(default=None),
    file_type: Optional[str] = Query(default=None),
    date_range: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """HTMX partial endpoint - returns only the file table HTML."""
    conditions = _build_file_query(search, file_type, date_range, current_user_id=user.user_id, current_user_role=user.role)

    count_stmt = select(File)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))

    total_result = await db.execute(count_stmt)
    all_files = total_result.scalars().all()
    total = len(all_files)

    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    stmt = select(File).options(selectinload(File.parse_jobs)).order_by(File.created_at.desc()).offset(offset).limit(page_size)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    files = result.scalars().all()

    return templates.TemplateResponse(
        "partials/file_table.html",
        {
            "request": request,
            "files": files,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": offset,
            "search": search or "",
            "file_type": file_type or "",
            "date_range": date_range or "",
        },
    )


def _build_user_query(search: Optional[str], date_range: Optional[str] = None):
    """Build SQLAlchemy WHERE conditions from user search/filter params."""
    conditions = []
    if search:
        conditions.append(
            or_(
                User.user_id.ilike(f"%{search}%"),
                User.display_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )
    if date_range:
        try:
            days = int(date_range)
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            conditions.append(User.created_at >= cutoff)
        except ValueError:
            pass
    return conditions


@router.get("/account", response_class=HTMLResponse)
async def account_page(
    request: Request,
    search: Optional[str] = Query(default=None),
    date_range: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    conditions = _build_user_query(search, date_range)

    count_stmt = select(func.count()).select_from(User)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await db.execute(stmt)
    users = result.scalars().all()

    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "user": user,
            "current_user": user,
            "users": users,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": offset,
            "search": search or "",
            "date_range": date_range or "",
            "active_nav": "account",
        },
    )


@router.get("/api/partials/account-table", response_class=HTMLResponse)
async def account_table_partial(
    request: Request,
    search: Optional[str] = Query(default=None),
    date_range: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """HTMX partial endpoint - returns only the account user table HTML."""
    conditions = _build_user_query(search, date_range)

    count_stmt = select(func.count()).select_from(User)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await db.execute(stmt)
    users = result.scalars().all()

    return templates.TemplateResponse(
        "partials/account_user_table.html",
        {
            "request": request,
            "current_user": user,
            "users": users,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": offset,
            "search": search or "",
            "date_range": date_range or "",
        },
    )
