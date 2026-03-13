"""
백그라운드 동기화 태스크 - parse_jobs 상태를 parser-server와 주기적으로 동기화.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.config import settings
from app.constants import ACTIVE_PARSE_STATUSES, ParseJobStatus
from app.database import AsyncSessionLocal
from app.models.tables import ParseJob

logger = logging.getLogger(__name__)

_TIMEOUT_THRESHOLD_HOURS = 24


async def _sync_one_job(parser_client, job_id: str, parser_job_id: str) -> dict | None:
    """단일 job에 대해 parser-server 상태를 조회하여 반환. 실패 시 None 반환."""
    try:
        status_data = await parser_client.get_job_status(parser_job_id)
        return status_data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"_not_found": True}
        logger.warning(f"job {job_id} 상태 조회 HTTP 오류: {e}")
        return None
    except Exception as e:
        logger.warning(f"job {job_id} 상태 조회 실패: {e}")
        return None


def _map_parser_status(parser_status: str) -> str:
    """parser-server의 status 값을 admin DB status로 매핑."""
    mapping = {
        "pending": ParseJobStatus.PENDING.value,
        "processing": ParseJobStatus.PROCESSING.value,
        "completed": ParseJobStatus.COMPLETED.value,
        "failed": ParseJobStatus.FAILED.value,
    }
    return mapping.get(parser_status, ParseJobStatus.ERROR.value)


async def _process_jobs_batch(parser_client, jobs: list[ParseJob]) -> None:
    """미완료 job 배치를 parser-server와 동기화."""
    semaphore = asyncio.Semaphore(settings.PARSE_MAX_CONCURRENT_CHECKS)
    now = datetime.now(timezone.utc)

    async def sync_with_semaphore(job: ParseJob):
        async with semaphore:
            return job, await _sync_one_job(parser_client, str(job.id), job.parser_job_id)

    tasks = [sync_with_semaphore(job) for job in jobs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    async with AsyncSessionLocal() as db:
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"배치 처리 중 예외 발생: {result}")
                continue

            job, status_data = result

            # DB에서 최신 job 상태를 다시 조회 (stale 방지)
            db_result = await db.execute(select(ParseJob).where(ParseJob.id == job.id))
            db_job = db_result.scalar_one_or_none()
            if db_job is None:
                continue

            if status_data is None:
                # 조회 실패 - retry_failure_count 증가
                db_job.retry_failure_count += 1
                if db_job.retry_failure_count >= 3:
                    db_job.status = ParseJobStatus.ERROR.value
                    db_job.error_message = "3회 연속 상태 조회 실패로 error 상태로 전환"
                    logger.warning(
                        f"job {db_job.id}: 3회 연속 실패, status=error로 전환"
                    )
            elif status_data.get("_not_found"):
                # parser-server에 해당 job이 없음
                db_job.status = ParseJobStatus.LOST.value
                db_job.error_message = "parser-server에서 job을 찾을 수 없음"
                logger.warning(f"job {db_job.id} (parser_job_id={db_job.parser_job_id}): parser-server에서 찾을 수 없어 lost 처리")
            else:
                # 타임아웃 체크 (24시간 초과 processing)
                created_at = db_job.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if (
                    db_job.status == ParseJobStatus.PROCESSING.value
                    and (now - created_at) > timedelta(hours=_TIMEOUT_THRESHOLD_HOURS)
                ):
                    db_job.status = ParseJobStatus.TIMEOUT.value
                    db_job.error_message = f"24시간 초과로 timeout 처리 (created_at={db_job.created_at})"
                    logger.warning(f"job {db_job.id}: 24시간 초과 timeout 처리")
                else:
                    # 정상 상태 갱신
                    new_status = _map_parser_status(status_data.get("status", ""))
                    db_job.status = new_status
                    db_job.retry_failure_count = 0  # 성공 시 초기화

                    parser_error = status_data.get("error")
                    if parser_error:
                        db_job.error_message = parser_error

                    if new_status in (ParseJobStatus.COMPLETED.value, ParseJobStatus.FAILED.value):
                        if db_job.completed_at is None:
                            db_job.completed_at = now
                        logger.info(f"job {db_job.id}: status={new_status} 완료 처리")

        await db.commit()


async def background_sync_loop(app) -> None:
    """백그라운드 동기화 루프. PARSE_POLL_INTERVAL_SECONDS 간격으로 미완료 job 동기화."""
    logger.info(
        f"백그라운드 동기화 루프 시작 (폴링 간격: {settings.PARSE_POLL_INTERVAL_SECONDS}초)"
    )

    while True:
        try:
            await asyncio.sleep(settings.PARSE_POLL_INTERVAL_SECONDS)

            parser_client = getattr(app.state, "parser_client", None)
            if parser_client is None:
                logger.debug("parser_client 없음, 이번 사이클 건너뜀")
                continue

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ParseJob).where(
                        ParseJob.status.in_(list(ACTIVE_PARSE_STATUSES))
                    )
                )
                jobs = result.scalars().all()

            if not jobs:
                logger.debug("동기화 대상 미완료 job 없음")
                continue

            logger.debug(f"동기화 대상 job {len(jobs)}건 처리 시작")
            await _process_jobs_batch(parser_client, list(jobs))

        except asyncio.CancelledError:
            logger.info("백그라운드 동기화 루프 취소됨")
            raise
        except httpx.ConnectError as e:
            logger.warning(f"parser-server 연결 실패, 이번 사이클 건너뜀: {e}")
        except Exception as e:
            logger.exception(f"백그라운드 동기화 루프 예외 발생: {e}")


async def resync_pending_jobs(app) -> None:
    """서버 재시작 시 미완료 job 전체를 parser-server와 재동기화."""
    parser_client = getattr(app.state, "parser_client", None)
    if parser_client is None:
        logger.warning("resync_pending_jobs: parser_client 없음, 재동기화 건너뜀")
        return

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ParseJob).where(
                    ParseJob.status.in_(list(ACTIVE_PARSE_STATUSES))
                )
            )
            jobs = result.scalars().all()

        if not jobs:
            logger.info("resync_pending_jobs: 재동기화 대상 job 없음")
            return

        logger.info(f"resync_pending_jobs: 미완료 job {len(jobs)}건 재동기화 시작")
        await _process_jobs_batch(parser_client, list(jobs))
        logger.info("resync_pending_jobs: 재동기화 완료")

    except httpx.ConnectError as e:
        logger.warning(f"resync_pending_jobs: parser-server 연결 실패, 건너뜀: {e}")
    except Exception as e:
        logger.exception(f"resync_pending_jobs: 재동기화 중 예외 발생: {e}")
