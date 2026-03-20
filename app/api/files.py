import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse as FastAPIFileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import Category
from app.database import get_db
from app.dependencies import require_auth
from app.models.tables import File as FileModel
from app.models.tables import User as UserModel
from app.schemas.file import FileListResponse, FileResponse, FileUpdate
from app.services import file_service

router = APIRouter(prefix="/api/files", tags=["files"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_model=FileListResponse)
async def list_files(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_auth),
):
    return await file_service.get_files(
        db,
        search=search,
        category=category,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )


@router.post("/upload", status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    category: Category = Form(default=Category.UNCATEGORIZED),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_auth),
):
    result = await file_service.upload_file(db, file, category, uploader=user.display_name)

    # HTMX 요청이면 파일 테이블 HTML partial 반환
    if request.headers.get("HX-Request"):
        stmt = select(FileModel).options(selectinload(FileModel.parse_jobs)).order_by(FileModel.created_at.desc()).limit(20)
        db_result = await db.execute(stmt)
        files = db_result.scalars().all()

        total_stmt = select(FileModel)
        total_result = await db.execute(total_stmt)
        total = len(total_result.scalars().all())
        total_pages = (total + 19) // 20 if total > 0 else 0

        return templates.TemplateResponse(
            "partials/file_table.html",
            {
                "request": request,
                "files": files,
                "total": total,
                "page": 1,
                "page_size": 20,
                "total_pages": total_pages,
                "offset": 0,
                "search": "",
                "file_type": "",
                "date_range": "",
            },
        )

    return result


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_auth),
):
    return await file_service.get_file(db, file_id)


@router.put("/{file_id}")
async def update_file(
    file_id: uuid.UUID,
    request: Request,
    body: FileUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_auth),
):
    result = await file_service.update_file(
        db,
        file_id,
        filename=body.filename,
        category=body.category.value if body.category else None,
    )

    # HTMX 요청이면 파일 행 HTML partial 반환
    if request.headers.get("HX-Request"):
        from app.models.tables import File as FileORM
        stmt = select(FileORM).options(selectinload(FileORM.parse_jobs)).where(FileORM.id == file_id)
        db_result = await db.execute(stmt)
        db_file = db_result.scalar_one()
        return templates.TemplateResponse(
            "partials/file_row.html",
            {"request": request, "file": db_file},
        )

    return result


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_auth),
):
    await file_service.delete_file(db, file_id)

    # HTMX 요청이면 갱신된 파일 테이블 HTML partial 반환
    if request.headers.get("HX-Request"):
        stmt = select(FileModel).options(selectinload(FileModel.parse_jobs)).order_by(FileModel.created_at.desc()).limit(20)
        db_result = await db.execute(stmt)
        files = db_result.scalars().all()

        total_stmt = select(FileModel)
        total_result = await db.execute(total_stmt)
        total = len(total_result.scalars().all())
        total_pages = (total + 19) // 20 if total > 0 else 0

        return templates.TemplateResponse(
            "partials/file_table.html",
            {
                "request": request,
                "files": files,
                "total": total,
                "page": 1,
                "page_size": 20,
                "total_pages": total_pages,
                "offset": 0,
                "search": "",
                "file_type": "",
                "date_range": "",
            },
        )

    return Response(status_code=204)


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_auth),
):
    db_file = await file_service.get_file_orm(db, file_id)
    stored = Path(db_file.stored_path)
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Physical file not found")
    return FastAPIFileResponse(
        path=str(stored),
        filename=db_file.filename,
        media_type=db_file.mime_type,
    )
