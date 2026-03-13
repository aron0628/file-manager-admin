from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.tables import File

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _build_file_query(
    search: Optional[str],
    file_type: Optional[str],
    date_range: Optional[str],
):
    """Build SQLAlchemy WHERE conditions from filter params."""
    conditions = []

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
):
    conditions = _build_file_query(search, file_type, date_range)

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
            "files": files,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "offset": offset,
            "search": search or "",
            "file_type": file_type or "",
            "date_range": date_range or "",
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
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
):
    """HTMX partial endpoint - returns only the file table HTML."""
    conditions = _build_file_query(search, file_type, date_range)

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
