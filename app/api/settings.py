from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.tables import User
from app.services.settings_service import (
    AVAILABLE_MODELS,
    SETTING_DEFINITIONS,
    get_all_settings,
    seed_defaults,
    upsert_setting,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Settings full page (admin only)."""
    all_settings = await get_all_settings(db)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "settings": all_settings,
            "available_models": AVAILABLE_MODELS,
            "active_nav": "settings",
        },
    )


@router.get("/api/partials/settings-form", response_class=HTMLResponse)
async def settings_form_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial: settings form only."""
    all_settings = await get_all_settings(db)
    return templates.TemplateResponse(
        "partials/settings_form.html",
        {
            "request": request,
            "settings": all_settings,
            "available_models": AVAILABLE_MODELS,
        },
    )


@router.put("/api/settings/{key}", response_class=HTMLResponse)
async def update_setting(
    request: Request,
    key: str,
    value: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Update a single setting value (admin only). Returns HTMX feedback snippet."""
    if key not in SETTING_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 설정 키입니다: {key}")
    try:
        await upsert_setting(db, key, value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return templates.TemplateResponse(
        "partials/settings_save_feedback.html",
        {"request": request, "key": key, "success": True},
    )


@router.post("/api/settings/seed", response_class=HTMLResponse)
async def seed_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Seed default values for missing settings."""
    await seed_defaults(db)
    all_settings = await get_all_settings(db)
    return templates.TemplateResponse(
        "partials/settings_form.html",
        {
            "request": request,
            "settings": all_settings,
            "available_models": AVAILABLE_MODELS,
        },
    )
