from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import AppSetting

# ---------------------------------------------------------------------------
# In-memory settings cache (loaded at startup, refreshed on every write)
# ---------------------------------------------------------------------------
_cache: dict[str, str] = {}


def get_cached_value(key: str) -> str:
    """Return the cached setting value, falling back to the definition default."""
    if key in _cache:
        return _cache[key]
    defn = SETTING_DEFINITIONS.get(key)
    return defn.default if defn else ""


def get_cached_int(key: str) -> int:
    """Convenience: return cached value as int."""
    return int(get_cached_value(key))


def get_cached_float(key: str) -> float:
    """Convenience: return cached value as float."""
    return float(get_cached_value(key))


def get_cached_bool(key: str) -> bool:
    """Convenience: return cached value as bool."""
    return get_cached_value(key).lower() == "true"


async def load_cache(db: AsyncSession) -> None:
    """Load all settings into the in-memory cache. Call once at startup."""
    global _cache
    result = await db.execute(select(AppSetting))
    rows = {row.key: row.value for row in result.scalars().all()}
    # Start with defaults, then overlay DB values
    _cache = {key: defn.default for key, defn in SETTING_DEFINITIONS.items()}
    _cache.update({k: v for k, v in rows.items() if k in SETTING_DEFINITIONS})


def _refresh_cache_key(key: str, value: str) -> None:
    """Update a single key in the cache after a DB write."""
    if key in SETTING_DEFINITIONS:
        _cache[key] = value

AVAILABLE_MODELS: dict[str, list[tuple[str, str]]] = {
    "OpenAI": [
        ("openai/gpt-5.4-mini", "GPT-5.4 Mini"),
        ("openai/gpt-5.4-nano", "GPT-5.4 Nano"),
        ("openai/gpt-4.1-mini", "GPT-4.1 Mini"),
        ("openai/gpt-4.1-nano", "GPT-4.1 Nano"),
        ("openai/gpt-4o", "GPT-4o"),
    ],
    "Google": [
        ("google_genai/gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
        ("google_genai/gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash-Lite"),
        ("google_genai/gemini-3-flash-preview", "Gemini 3 Flash"),
    ],
    "xAI": [
        ("xai/grok-4.20-0309-reasoning", "Grok 4.20 Reasoning"),
        ("xai/grok-4.20-0309-non-reasoning", "Grok 4.20 Non-Reasoning"),
        ("xai/grok-4.20-multi-agent-0309", "Grok 4.20 Multi-Agent"),
        ("xai/grok-4-1-fast-reasoning", "Grok 4.1 Fast Reasoning"),
        ("xai/grok-4-1-fast-non-reasoning", "Grok 4.1 Fast Non-Reasoning"),
    ],
}

# Tab → group mapping for the settings UI
TAB_GROUPS: list[tuple[str, str, list[str]]] = [
    ("agent", "에이전트", ["에이전트 설정", "기능 플래그"]),
    ("parsing", "문서 파싱", ["동기화", "청크", "RAPTOR", "키워드"]),
    ("system", "시스템", ["업로드 설정", "보안 설정"]),
]

AVAILABLE_MIME_TYPES: list[tuple[str, str]] = [
    ("application/pdf", "PDF"),
    ("image/png", "PNG"),
    ("image/jpeg", "JPEG"),
    ("image/gif", "GIF"),
    ("image/webp", "WebP"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "DOCX"),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "XLSX"),
    ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "PPTX"),
    ("text/plain", "TXT"),
    ("text/csv", "CSV"),
]

MODEL_SELECTOR_KEYS = {"model", "summarization_model", "rag_grading_model"}
BOOLEAN_KEYS = {"enable_raptor", "enable_hybrid_search", "enable_keyword_extraction"}


@dataclass
class SettingDefinition:
    """Metadata for a known application setting."""

    key: str
    default: str
    description: str
    group: str
    setting_type: str  # "model_select" | "boolean" | "text"


SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    "model": SettingDefinition(
        key="model",
        default="openai/gpt-4.1-mini",
        description="에이전트 메인 대화에 사용하는 LLM 모델",
        group="에이전트 설정",
        setting_type="model_select",
    ),
    "summarization_model": SettingDefinition(
        key="summarization_model",
        default="openai/gpt-4.1-mini",
        description="대화 요약 + 제목 생성에 사용하는 LLM 모델",
        group="에이전트 설정",
        setting_type="model_select",
    ),
    "rag_grading_model": SettingDefinition(
        key="rag_grading_model",
        default="openai/gpt-4.1-mini",
        description="RAG 문서 평가 + 쿼리 재작성에 사용하는 LLM 모델",
        group="에이전트 설정",
        setting_type="model_select",
    ),
    "max_search_results": SettingDefinition(
        key="max_search_results",
        default="10",
        description="검색 도구가 반환하는 최대 결과 수",
        group="에이전트 설정",
        setting_type="text",
    ),
    "summary_message_threshold": SettingDefinition(
        key="summary_message_threshold",
        default="20",
        description="대화 요약을 트리거하는 메시지 수 임계값",
        group="에이전트 설정",
        setting_type="text",
    ),
    "enable_raptor": SettingDefinition(
        key="enable_raptor",
        default="true",
        description="RAPTOR 계층적 문서 인덱싱 활성화 여부",
        group="RAPTOR",
        setting_type="boolean",
    ),
    "enable_hybrid_search": SettingDefinition(
        key="enable_hybrid_search",
        default="true",
        description="하이브리드 검색(벡터 + BM25) 활성화 여부",
        group="기능 플래그",
        setting_type="boolean",
    ),
    "hybrid_alpha": SettingDefinition(
        key="hybrid_alpha",
        default="0.7",
        description="하이브리드 검색에서 벡터 검색 가중치 (0.0~1.0)",
        group="기능 플래그",
        setting_type="text",
    ),
    "bm25_top_k": SettingDefinition(
        key="bm25_top_k",
        default="20",
        description="BM25 키워드 검색에서 반환할 상위 결과 수",
        group="기능 플래그",
        setting_type="text",
    ),
    # -- 업로드 설정 --
    "max_upload_size_mb": SettingDefinition(
        key="max_upload_size_mb",
        default="100",
        description="최대 업로드 파일 크기 (MB)",
        group="업로드 설정",
        setting_type="text",
    ),
    "allowed_mime_types": SettingDefinition(
        key="allowed_mime_types",
        default="application/pdf",
        description="업로드를 허용할 파일 형식을 선택하세요",
        group="업로드 설정",
        setting_type="mime_select",
    ),
    # -- 파싱 설정 --
    "parse_poll_interval_seconds": SettingDefinition(
        key="parse_poll_interval_seconds",
        default="10",
        description="백그라운드 파싱 상태 동기화 폴링 간격 (초)",
        group="동기화",
        setting_type="text",
    ),
    "parse_max_concurrent_checks": SettingDefinition(
        key="parse_max_concurrent_checks",
        default="20",
        description="동기화 사이클당 최대 동시 상태 조회 수",
        group="동기화",
        setting_type="text",
    ),
    "chunk_size": SettingDefinition(
        key="chunk_size",
        default="1000",
        description="텍스트 청크 크기 (문자 수). 파싱 서버에 전달됩니다.",
        group="청크",
        setting_type="text",
    ),
    "chunk_overlap": SettingDefinition(
        key="chunk_overlap",
        default="200",
        description="텍스트 청크 오버랩 (문자 수). 파싱 서버에 전달됩니다.",
        group="청크",
        setting_type="text",
    ),
    "max_chunks_for_raptor": SettingDefinition(
        key="max_chunks_for_raptor",
        default="2000",
        description="RAPTOR 처리 최대 청크 수",
        group="RAPTOR",
        setting_type="text",
    ),
    "entity_extractor_max_concurrency": SettingDefinition(
        key="entity_extractor_max_concurrency",
        default="3",
        description="이미지/테이블 엔티티 추출 최대 동시 요청 수",
        group="RAPTOR",
        setting_type="text",
    ),
    "enable_keyword_extraction": SettingDefinition(
        key="enable_keyword_extraction",
        default="true",
        description="키워드 자동 추출 활성화 여부",
        group="키워드",
        setting_type="boolean",
    ),
    # -- 보안 설정 --
    "session_expire_hours": SettingDefinition(
        key="session_expire_hours",
        default="24",
        description="세션 만료 시간 (시간 단위). 값을 줄이면 기존 로그인 세션이 즉시 만료됩니다.",
        group="보안 설정",
        setting_type="text",
    ),
}


@dataclass
class SettingDTO:
    """Transfer object combining DB value with setting metadata."""

    key: str
    value: str
    description: str
    group: str
    setting_type: str
    updated_at: Any | None = None


async def get_setting(db: AsyncSession, key: str) -> str | None:
    """Return the stored value for a setting key, or None if not set."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row is not None else None


async def get_all_settings(db: AsyncSession) -> dict[str, SettingDTO]:
    """Return all known settings with metadata, falling back to defaults for unset keys."""
    result = await db.execute(select(AppSetting))
    rows: dict[str, AppSetting] = {row.key: row for row in result.scalars().all()}

    settings: dict[str, SettingDTO] = {}
    for key, defn in SETTING_DEFINITIONS.items():
        row = rows.get(key)
        settings[key] = SettingDTO(
            key=key,
            value=row.value if row is not None else defn.default,
            description=defn.description,
            group=defn.group,
            setting_type=defn.setting_type,
            updated_at=row.updated_at if row is not None else None,
        )
    return settings


async def upsert_setting(db: AsyncSession, key: str, value: str) -> None:
    """Insert or update a setting. Raises ValueError for unknown keys."""
    if key not in SETTING_DEFINITIONS:
        raise ValueError(f"알 수 없는 설정 키입니다: {key}")

    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        defn = SETTING_DEFINITIONS[key]
        row = AppSetting(
            key=key,
            value=value,
            description=defn.description,
        )
        db.add(row)
    else:
        row.value = value
    await db.commit()
    _refresh_cache_key(key, value)


async def seed_defaults(db: AsyncSession) -> None:
    """Insert default values for any settings that are not yet in the DB."""
    result = await db.execute(select(AppSetting))
    existing_keys = {row.key for row in result.scalars().all()}

    for key, defn in SETTING_DEFINITIONS.items():
        if key not in existing_keys:
            db.add(
                AppSetting(
                    key=key,
                    value=defn.default,
                    description=defn.description,
                )
            )
    await db.commit()
    await load_cache(db)


async def reset_to_defaults(db: AsyncSession) -> None:
    """Reset ALL settings to their default values, overwriting existing values."""
    result = await db.execute(select(AppSetting))
    existing: dict[str, AppSetting] = {row.key: row for row in result.scalars().all()}

    for key, defn in SETTING_DEFINITIONS.items():
        row = existing.get(key)
        if row is not None:
            row.value = defn.default
        else:
            db.add(
                AppSetting(
                    key=key,
                    value=defn.default,
                    description=defn.description,
                )
            )
    await db.commit()
    await load_cache(db)
