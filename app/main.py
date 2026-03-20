import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api import auth, files, parse
from app.api.pages import router as pages_router
from app.config import settings
from app.dependencies import _AuthRedirectException
from app.schemas.file import HealthResponse
from app.services.background_sync import background_sync_loop, resync_pending_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: AsyncDocumentParserClient 생명주기 관리
    from document_parser_client import AsyncDocumentParserClient

    try:
        async with AsyncDocumentParserClient(api_url=settings.PARSER_SERVER_URL) as client:
            app.state.parser_client = client
            logger.info(f"AsyncDocumentParserClient 연결됨: {settings.PARSER_SERVER_URL}")

            # 서버 재시작 시 미완료 작업 재동기화
            await resync_pending_jobs(app)

            # 백그라운드 동기화 태스크 시작
            sync_task = asyncio.create_task(background_sync_loop(app))
            logger.info("백그라운드 동기화 태스크 시작됨")

            yield

            # shutdown: 백그라운드 태스크 취소
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass
            logger.info("백그라운드 동기화 태스크 종료됨")

    except httpx.ConnectError as e:
        logger.warning(
            f"parser-server 연결 실패 ({settings.PARSER_SERVER_URL}): {e}. "
            "파싱 기능을 사용할 수 없습니다. parser-server를 실행한 후 서버를 재시작하세요."
        )
        app.state.parser_client = None
        sync_task = asyncio.create_task(background_sync_loop(app))
        yield
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        logger.exception(f"AsyncDocumentParserClient 초기화 중 예외 발생: {e}")
        app.state.parser_client = None
        sync_task = asyncio.create_task(background_sync_loop(app))
        yield
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="File Manager Admin",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(_AuthRedirectException)
async def auth_redirect_handler(request, exc):
    return exc.response


app.include_router(auth.router)
app.include_router(pages_router)
app.include_router(files.router)
app.include_router(parse.router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")
