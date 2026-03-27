from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.tables import User
from app.services.settings_service import (
    AVAILABLE_MIME_TYPES,
    AVAILABLE_MODELS,
    BOOLEAN_KEYS,
    SETTING_DEFINITIONS,
    TAB_GROUPS,
    get_all_settings,
    get_cached_value,
    load_cache,
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
            "available_mime_types": AVAILABLE_MIME_TYPES,
            "tab_groups": TAB_GROUPS,
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
            "available_mime_types": AVAILABLE_MIME_TYPES,
            "tab_groups": TAB_GROUPS,
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


@router.post("/api/settings/batch", response_class=HTMLResponse)
async def batch_update_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Batch update all settings from the form (admin only)."""
    form_data = await request.form()
    active_tab = form_data.get("_active_tab", "agent")

    # Detect session_expire_hours decrease for warning
    old_session_hours = get_cached_value("session_expire_hours")
    session_warning = False

    for key in SETTING_DEFINITIONS:
        if key in form_data:
            value = form_data[key]
            # For checkboxes: if both hidden (false) and checked (true) are sent,
            # the browser sends the checked value last, so getlist picks it up.
            if key in BOOLEAN_KEYS:
                values = form_data.getlist(key)
                value = values[-1] if values else "false"
            await upsert_setting(db, key, str(value))

    # Check if session_expire_hours was decreased
    new_session_hours = get_cached_value("session_expire_hours")
    if int(new_session_hours) < int(old_session_hours):
        session_warning = True

    all_settings = await get_all_settings(db)
    return templates.TemplateResponse(
        "partials/settings_form.html",
        {
            "request": request,
            "settings": all_settings,
            "available_models": AVAILABLE_MODELS,
            "available_mime_types": AVAILABLE_MIME_TYPES,
            "tab_groups": TAB_GROUPS,
            "save_success": True,
            "session_warning": session_warning,
            "active_tab": active_tab,
        },
    )


@router.post("/api/settings/seed", response_class=HTMLResponse)
async def preview_defaults(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """Return the settings form populated with default values (does NOT save to DB)."""
    from app.services.settings_service import SettingDTO
    default_settings: dict[str, SettingDTO] = {
        key: SettingDTO(
            key=key,
            value=defn.default,
            description=defn.description,
            group=defn.group,
            setting_type=defn.setting_type,
        )
        for key, defn in SETTING_DEFINITIONS.items()
    }
    return templates.TemplateResponse(
        "partials/settings_form.html",
        {
            "request": request,
            "settings": default_settings,
            "available_models": AVAILABLE_MODELS,
            "available_mime_types": AVAILABLE_MIME_TYPES,
            "tab_groups": TAB_GROUPS,
        },
    )
