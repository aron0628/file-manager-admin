"""
Parse service - document-parser-client 연동 (Phase 4 완성).
"""
import logging
import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import ParseJobStatus
from app.models.tables import File, ParseJob
from app.schemas.file import ParseJobResponse
from app.services import file_service
from app.services.settings_service import get_cached_bool, get_cached_int

logger = logging.getLogger(__name__)

_PARSE_RESULTS_DIR = Path(settings.PARSE_RESULT_DIR)


async def start_parse(
    db: AsyncSession,
    file_id: uuid.UUID,
    parser_client=None,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> ParseJobResponse:
    """파싱 작업 시작: parser-server에 PDF 전달 후 parse_jobs 레코드 생성."""
    db_file = await file_service.get_file_orm(
        db, file_id, current_user_id=current_user_id, current_user_role=current_user_role
    )

    if parser_client is None:
        raise HTTPException(
            status_code=503,
            detail="Parser server is not connected. Start the document-parser-server and restart.",
        )

    stored_path = Path(db_file.stored_path)
    if not stored_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Stored file not found on disk: {stored_path}",
        )

    try:
        parse_result = await parser_client.parse_pdf(
            str(stored_path),
            enable_raptor=get_cached_bool("enable_raptor"),
            chunk_size=get_cached_int("chunk_size") if get_cached_int("chunk_size") else None,
            chunk_overlap=get_cached_int("chunk_overlap") if get_cached_int("chunk_overlap") else None,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to parser-server. Please check the server is running.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Parser server error: {e.response.status_code} {e.response.text}",
        )
    except Exception as e:
        logger.exception(f"parse_pdf 호출 중 예외: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error calling parser: {e}")

    parser_job_id = parse_result.get("job_id")
    if not parser_job_id:
        raise HTTPException(
            status_code=502,
            detail=f"Parser server returned no job_id: {parse_result}",
        )

    job = ParseJob(
        file_id=file_id,
        parser_job_id=parser_job_id,
        status=ParseJobStatus.PENDING.value,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    logger.info(f"파싱 작업 생성: file_id={file_id}, parser_job_id={parser_job_id}, job_id={job.id}")
    return ParseJobResponse.model_validate(job)


async def get_parse_status(
    db: AsyncSession,
    file_id: uuid.UUID,
    parser_client=None,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> ParseJobResponse:
    """
    파싱 상태 조회 - HTMX 폴링용 DB 캐시 반환.
    백그라운드 태스크가 parser-server와 동기화를 담당하므로 DB 상태만 반환.
    parser_client가 있어도 여기서는 DB 캐시만 반환 (read-through는 bg sync 담당).
    """
    # 소유권 검증
    await file_service.get_file_orm(
        db, file_id, current_user_id=current_user_id, current_user_role=current_user_role
    )

    result = await db.execute(
        select(ParseJob)
        .where(ParseJob.file_id == file_id)
        .order_by(ParseJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="No parse job found for this file")

    return ParseJobResponse.model_validate(job)


async def get_parse_result(
    db: AsyncSession,
    file_id: uuid.UUID,
    parser_client=None,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> str:
    """완료된 파싱 결과의 ZIP 파일 경로 반환. result_path 없으면 parser-server에서 다운로드."""
    # 소유권 검증
    await file_service.get_file_orm(
        db, file_id, current_user_id=current_user_id, current_user_role=current_user_role
    )

    result = await db.execute(
        select(ParseJob)
        .where(ParseJob.file_id == file_id)
        .order_by(ParseJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="No parse job found for this file")

    if job.status != ParseJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Parse job is not completed. Current status: {job.status}",
        )

    # 이미 다운로드된 result_path가 있으면 바로 반환
    if job.result_path and Path(job.result_path).exists():
        return job.result_path

    # result_path 없거나 파일이 없으면 parser-server에서 다운로드
    if parser_client is None:
        raise HTTPException(
            status_code=503,
            detail="Parser server is not connected. Cannot download result.",
        )

    _PARSE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        zip_path, _ = await parser_client.download_result(
            job_id=job.parser_job_id,
            output_dir=str(_PARSE_RESULTS_DIR),
            extract=False,
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to parser-server to download result.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Parser server error during download: {e.response.status_code}",
        )
    except Exception as e:
        logger.exception(f"download_result 호출 중 예외: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error downloading result: {e}")

    # DB에 result_path 저장
    job.result_path = str(zip_path)
    await db.commit()

    logger.info(f"파싱 결과 다운로드 완료: job_id={job.id}, zip_path={zip_path}")
    return str(zip_path)


async def retry_raptor(
    db: AsyncSession,
    file_id: uuid.UUID,
    parser_client=None,
    current_user_id: str | None = None,
    current_user_role: str | None = None,
) -> ParseJobResponse:
    """완료된 파싱 작업에서 RAPTOR만 재실행 요청."""
    # 소유권 검증
    await file_service.get_file_orm(
        db, file_id, current_user_id=current_user_id, current_user_role=current_user_role
    )

    result = await db.execute(
        select(ParseJob)
        .where(ParseJob.file_id == file_id)
        .order_by(ParseJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="No parse job found for this file")

    if job.status != ParseJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=409,
            detail=f"RAPTOR retry requires completed parse job. Current status: {job.status}",
        )

    if parser_client is None:
        raise HTTPException(
            status_code=503,
            detail="Parser server is not connected. Cannot retry RAPTOR.",
        )

    try:
        await parser_client.retry_raptor(job.parser_job_id)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to parser-server. Please check the server is running.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Parser server error: {e.response.status_code} {e.response.text}",
        )
    except Exception as e:
        logger.exception(f"retry_raptor 호출 중 예외: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error calling parser: {e}")

    job.raptor_status = "processing"
    await db.commit()
    await db.refresh(job)

    logger.info(f"RAPTOR 재실행 요청: file_id={file_id}, parser_job_id={job.parser_job_id}")
    return ParseJobResponse.model_validate(job)
