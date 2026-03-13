import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.constants import Category, ParseJobStatus


class FileBase(BaseModel):
    filename: str
    category: Category = Category.UNCATEGORIZED
    uploader: str = "Admin"


class FileCreate(FileBase):
    stored_path: str
    file_size: int
    mime_type: str


class FileUpdate(BaseModel):
    filename: str | None = None
    category: Category | None = None
    uploader: str | None = None


class FileResponse(BaseModel):
    id: uuid.UUID
    filename: str
    stored_path: str
    file_size: int
    mime_type: str
    category: str
    uploader: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ParseJobResponse(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    parser_job_id: str
    status: str
    error_message: str | None = None
    result_path: str | None = None
    retry_failure_count: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    items: list[FileResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
