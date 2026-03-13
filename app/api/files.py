import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Category
from app.database import get_db
from app.schemas.file import FileListResponse, FileResponse, FileUpdate
from app.services import file_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=FileListResponse)
async def list_files(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
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


@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    category: Category = Form(default=Category.UNCATEGORIZED),
    db: AsyncSession = Depends(get_db),
):
    return await file_service.upload_file(db, file, category)


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await file_service.get_file(db, file_id)


@router.put("/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: uuid.UUID,
    body: FileUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await file_service.update_file(
        db,
        file_id,
        filename=body.filename,
        category=body.category.value if body.category else None,
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await file_service.delete_file(db, file_id)


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
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
