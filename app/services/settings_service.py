from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import AppSetting

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

MODEL_SELECTOR_KEYS = {"model", "summarization_model", "rag_grading_model"}
BOOLEAN_KEYS = {"enable_raptor", "enable_hybrid_search"}


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
        group="Agent Configuration",
        setting_type="model_select",
    ),
    "summarization_model": SettingDefinition(
        key="summarization_model",
        default="openai/gpt-4.1-mini",
        description="대화 요약 + 제목 생성에 사용하는 LLM 모델",
        group="Agent Configuration",
        setting_type="model_select",
    ),
    "rag_grading_model": SettingDefinition(
        key="rag_grading_model",
        default="openai/gpt-4.1-mini",
        description="RAG 문서 평가 + 쿼리 재작성에 사용하는 LLM 모델",
        group="Agent Configuration",
        setting_type="model_select",
    ),
    "max_search_results": SettingDefinition(
        key="max_search_results",
        default="10",
        description="검색 도구가 반환하는 최대 결과 수",
        group="Agent Configuration",
        setting_type="text",
    ),
    "summary_message_threshold": SettingDefinition(
        key="summary_message_threshold",
        default="20",
        description="대화 요약을 트리거하는 메시지 수 임계값",
        group="Agent Configuration",
        setting_type="text",
    ),
    "enable_raptor": SettingDefinition(
        key="enable_raptor",
        default="true",
        description="RAPTOR 계층적 문서 인덱싱 활성화 여부",
        group="Feature Flags",
        setting_type="boolean",
    ),
    "enable_hybrid_search": SettingDefinition(
        key="enable_hybrid_search",
        default="true",
        description="하이브리드 검색(벡터 + BM25) 활성화 여부",
        group="Feature Flags",
        setting_type="boolean",
    ),
    "hybrid_alpha": SettingDefinition(
        key="hybrid_alpha",
        default="0.7",
        description="하이브리드 검색에서 벡터 검색 가중치 (0.0~1.0)",
        group="Feature Flags",
        setting_type="text",
    ),
    "bm25_top_k": SettingDefinition(
        key="bm25_top_k",
        default="20",
        description="BM25 키워드 검색에서 반환할 상위 결과 수",
        group="Feature Flags",
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
