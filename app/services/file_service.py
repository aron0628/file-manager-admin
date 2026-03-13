import uuid
from datetime import date
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import Category
from app.models.tables import File
from app.schemas.file import FileListResponse, FileResponse, FileUpdate

UPLOADS_DIR = Path(settings.UPLOAD_DIR)


def _get_safe_stored_path(file_uuid: uuid.UUID, ext: str) -> Path:
    """Return a safe stored path inside UPLOADS_DIR. Raises if outside uploads/."""
    filename = f"{file_uuid}{ext}"
    stored = (UPLOADS_DIR / filename).resolve()
    uploads_resolved = UPLOADS_DIR.resolve()
    if not str(stored).startswith(str(uploads_resolved)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return stored


async def upload_file(
    db: AsyncSession,
    file: UploadFile,
    category: Category,
) -> FileResponse:
    # MIME type validation
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {file.content_type}. Allowed: {settings.ALLOWED_MIME_TYPES}",
        )

    # Read content and validate size
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Determine extension from original filename
    original_filename = file.filename or "upload"
    suffix = Path(original_filename).suffix.lower()
    if not suffix:
        suffix = ".pdf"

    # UUID-based stored_path (path traversal safe)
    file_uuid = uuid.uuid4()
    stored_path = _get_safe_stored_path(file_uuid, suffix)

    # Ensure uploads directory exists
    UPLOADS_DIR.mkdir(exist_ok=True)

    # Write physical file
    stored_path.write_bytes(content)

    # DB record
    relative_path = f"uploads/{file_uuid}{suffix}"
    db_file = File(
        filename=original_filename,
        stored_path=relative_path,
        file_size=len(content),
        mime_type=file.content_type,
        category=category.value,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    return FileResponse.model_validate(db_file)


async def get_files(
    db: AsyncSession,
    search: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    per_page: int = 20,
) -> FileListResponse:
    stmt = select(File)
    filters = []

    if search:
        filters.append(File.filename.ilike(f"%{search}%"))
    if category:
        filters.append(File.category == category)
    if date_from:
        filters.append(func.date(File.created_at) >= date_from)
    if date_to:
        filters.append(func.date(File.created_at) <= date_to)

    if filters:
        stmt = stmt.where(and_(*filters))

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginated results
    offset = (page - 1) * per_page
    stmt = stmt.order_by(File.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(stmt)
    files = result.scalars().all()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return FileListResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=per_page,
        total_pages=total_pages,
    )


async def get_file(db: AsyncSession, file_id: uuid.UUID) -> FileResponse:
    result = await db.execute(select(File).where(File.id == file_id))
    db_file = result.scalar_one_or_none()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse.model_validate(db_file)


async def get_file_orm(db: AsyncSession, file_id: uuid.UUID) -> File:
    result = await db.execute(select(File).where(File.id == file_id))
    db_file = result.scalar_one_or_none()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


async def update_file(
    db: AsyncSession,
    file_id: uuid.UUID,
    filename: str | None = None,
    category: str | None = None,
) -> FileResponse:
    db_file = await get_file_orm(db, file_id)

    if filename is not None:
        db_file.filename = filename
    if category is not None:
        # Validate category
        valid_values = [c.value for c in Category]
        if category not in valid_values:
            raise HTTPException(
                status_code=422, detail=f"Invalid category. Allowed: {valid_values}"
            )
        db_file.category = category

    await db.commit()
    await db.refresh(db_file)
    return FileResponse.model_validate(db_file)


async def delete_file(db: AsyncSession, file_id: uuid.UUID) -> None:
    db_file = await get_file_orm(db, file_id)

    # Delete physical file
    stored = Path(db_file.stored_path)
    # Verify it's inside uploads/ before deleting (path traversal guard)
    uploads_resolved = UPLOADS_DIR.resolve()
    try:
        stored_resolved = stored.resolve()
        if str(stored_resolved).startswith(str(uploads_resolved)) and stored.exists():
            stored.unlink()
    except Exception:
        pass  # Best effort; proceed with DB deletion

    await db.delete(db_file)
    await db.commit()
