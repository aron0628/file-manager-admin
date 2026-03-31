import logging
import uuid
from datetime import date
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.constants import Category, UserRole
from app.services.settings_service import get_cached_int, get_cached_value
from app.models.tables import File
from app.schemas.file import FileListResponse, FileResponse, FileUpdate

logger = logging.getLogger(__name__)

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
    uploader: str = "Admin",
    owner_id: str | None = None,
) -> FileResponse:
    # MIME type validation (DB setting: comma-separated string)
    allowed_types = [t.strip() for t in get_cached_value("allowed_mime_types").split(",")]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {file.content_type}. Allowed: {allowed_types}",
        )

    # Read content and validate size (DB setting)
    content = await file.read()
    max_upload_mb = get_cached_int("max_upload_size_mb")
    max_bytes = max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"파일이 너무 큽니다. 최대 {max_upload_mb}MB까지 업로드 가능합니다.",
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
        uploader=uploader,
        owner_id=owner_id,
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
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> FileListResponse:
    stmt = select(File)
    filters = []

    # 소유권 필터: admin이 아니면 본인 파일만
    if current_user_role != UserRole.ADMIN.value and current_user_id:
        filters.append(File.owner_id == current_user_id)

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


async def get_file(
    db: AsyncSession,
    file_id: uuid.UUID,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> FileResponse:
    result = await db.execute(select(File).where(File.id == file_id))
    db_file = result.scalar_one_or_none()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    # 소유권 검증: admin이 아니면 본인 파일만
    if current_user_role != UserRole.ADMIN.value and current_user_id:
        if db_file.owner_id != current_user_id:
            raise HTTPException(status_code=404, detail="File not found")
    return FileResponse.model_validate(db_file)


async def get_file_orm(
    db: AsyncSession,
    file_id: uuid.UUID,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> File:
    result = await db.execute(select(File).where(File.id == file_id))
    db_file = result.scalar_one_or_none()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    # 소유권 검증: admin이 아니면 본인 파일만
    if current_user_role != UserRole.ADMIN.value and current_user_id:
        if db_file.owner_id != current_user_id:
            raise HTTPException(status_code=404, detail="File not found")
    return db_file


async def update_file(
    db: AsyncSession,
    file_id: uuid.UUID,
    filename: str | None = None,
    category: str | None = None,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> FileResponse:
    db_file = await get_file_orm(db, file_id, current_user_id=current_user_id, current_user_role=current_user_role)

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


async def delete_file(
    db: AsyncSession,
    file_id: uuid.UUID,
    parser_client=None,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> None:
    db_file = await get_file_orm(db, file_id, current_user_id=current_user_id, current_user_role=current_user_role)

    # parser-server 쪽 데이터 삭제 (document_embeddings, raptor_summaries 등)
    if parser_client is not None:
        stmt = select(File).options(selectinload(File.parse_jobs)).where(File.id == file_id)
        result = await db.execute(stmt)
        file_with_jobs = result.scalar_one()
        for job in file_with_jobs.parse_jobs:
            try:
                await parser_client.delete_job(job.parser_job_id)
            except Exception as e:
                logger.warning("parser-server job 삭제 실패 (job_id=%s): %s", job.parser_job_id, e)

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
