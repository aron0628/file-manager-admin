import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse as FastAPIFileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.file import ParseJobResponse
from app.services import parse_service

router = APIRouter(prefix="/api/files", tags=["parse"])
templates = Jinja2Templates(directory="app/templates")


def _get_parser_client(request: Request):
    return getattr(request.app.state, "parser_client", None)


@router.post("/{file_id}/parse", response_model=ParseJobResponse, status_code=202)
async def start_parse(
    file_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    parser_client = _get_parser_client(request)
    return await parse_service.start_parse(db, file_id, parser_client)


@router.get("/{file_id}/parse-status")
async def get_parse_status(
    file_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    파싱 상태 조회.
    HTMX 요청(HX-Request 헤더)이면 parse_status.html partial 반환.
    일반 요청이면 JSON 반환.
    """
    parser_client = _get_parser_client(request)

    # 404의 경우 parse_service에서 HTTPException을 발생시킴
    try:
        job = await parse_service.get_parse_status(db, file_id, parser_client)
    except HTTPException as e:
        # HTMX 요청이면 404도 partial로 반환 (parse_job=None, not-found 상태)
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                "partials/parse_status.html",
                {
                    "request": request,
                    "parse_job": None,
                    "file_id": str(file_id),
                },
                status_code=e.status_code,
            )
        raise

    # HTMX 요청이면 HTML partial 반환
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/parse_status.html",
            {
                "request": request,
                "parse_job": job,
                "file_id": str(file_id),
            },
        )

    return job


@router.get("/{file_id}/parse-result")
async def get_parse_result(
    file_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    parser_client = _get_parser_client(request)
    result_path = await parse_service.get_parse_result(db, file_id, parser_client)
    path = Path(result_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Result file not found on disk")
    return FastAPIFileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/zip",
    )
