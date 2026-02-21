from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_path_csv(value: str) -> list[Path]:
    return [Path(item.strip()).resolve() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Doppelganger"))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    backend_public_url: str = field(default_factory=lambda: os.getenv("BACKEND_PUBLIC_URL", "").strip())
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    log_raw_model_output: bool = field(
        default_factory=lambda: os.getenv("LOG_RAW_MODEL_OUTPUT", "true").lower() == "true"
    )
    log_max_chars: int = field(default_factory=lambda: int(os.getenv("LOG_MAX_CHARS", "6000")))
    wecom_corp_id: str = field(default_factory=lambda: os.getenv("WECOM_CORP_ID", "").strip())
    wecom_agent_id: int = field(default_factory=lambda: int(os.getenv("WECOM_AGENT_ID", "0")))
    wecom_secret: str = field(default_factory=lambda: os.getenv("WECOM_SECRET", "").strip())
    wecom_token: str = field(default_factory=lambda: os.getenv("WECOM_TOKEN", "").strip())
    wecom_encoding_aes_key: str = field(
        default_factory=lambda: os.getenv("WECOM_ENCODING_AES_KEY", "").strip()
    )
    wecom_proxy_url: str = field(default_factory=lambda: os.getenv("WECOM_PROXY_URL", "").strip())
    wecom_callback_path: str = field(
        default_factory=lambda: os.getenv("WECOM_CALLBACK_PATH", "/wecom/callback").strip()
    )
    wecom_merge_burst_gap_seconds: float = field(
        default_factory=lambda: float(os.getenv("WECOM_MERGE_BURST_GAP_SECONDS", "6.0"))
    )
    wecom_merge_idle_seconds: float = field(
        default_factory=lambda: float(os.getenv("WECOM_MERGE_IDLE_SECONDS", "1.2"))
    )
    wecom_merge_incomplete_extra_seconds: float = field(
        default_factory=lambda: float(os.getenv("WECOM_MERGE_INCOMPLETE_EXTRA_SECONDS", "1.0"))
    )
    wecom_merge_max_wait_seconds: float = field(
        default_factory=lambda: float(os.getenv("WECOM_MERGE_MAX_WAIT_SECONDS", "10.0"))
    )

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_pro_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_PRO_MODEL", "gemini-3-pro-preview")
    )
    gemini_flash_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_FLASH_MODEL", "gemini-3-pro-preview")
    )
    gemini_embedding_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    )
    gemini_embedding_dim: int = field(
        default_factory=lambda: int(os.getenv("GEMINI_EMBEDDING_DIM", "3072"))
    )
    gemini_embedding_text_source: str = field(
        default_factory=lambda: os.getenv("GEMINI_EMBEDDING_TEXT_SOURCE", "segment_text")
    )
    gemini_fallback_models: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv(
                "GEMINI_FALLBACK_MODELS",
                "gemini-3-pro-preview",
            )
        )
    )

    chat_data_path: Path = field(
        default_factory=lambda: Path(os.getenv("CHAT_DATA_PATH", "data/chat_data.json")).resolve()
    )
    bootstrap_allow_json_ingest: bool = field(
        default_factory=lambda: os.getenv("BOOTSTRAP_ALLOW_JSON_INGEST", "false").lower() == "true"
    )
    sqlite_path: Path = field(
        default_factory=lambda: Path(os.getenv("SQLITE_PATH", "runtime/doppelganger.db")).resolve()
    )
    style_profile_path: Path = field(
        default_factory=lambda: Path(os.getenv("STYLE_PROFILE_PATH", "runtime/style_profile.json")).resolve()
    )
    preference_profile_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("PREFERENCE_PROFILE_PATH", "runtime/preference_profile.json")
        ).resolve()
    )
    persona_profile_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("PERSONA_PROFILE_PATH", "runtime/persona_profile.json")
        ).resolve()
    )

    segment_ids_path: Path = field(
        default_factory=lambda: Path(os.getenv("SEGMENT_IDS_PATH", "runtime/rag_segment_ids.npy")).resolve()
    )
    segment_vectors_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("SEGMENT_VECTORS_PATH", "runtime/rag_segment_vectors.npy")
        ).resolve()
    )
    segment_index_meta_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("SEGMENT_INDEX_META_PATH", "runtime/rag_segment_index_meta.json")
        ).resolve()
    )

    target_sender: str = field(default_factory=lambda: os.getenv("TARGET_SENDER", "Doppelgänger"))
    user_sender_candidates: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("USER_SENDER_CANDIDATES", "dxa🥰,dxa??,dxa")
        )
    )
    dxa_persona_key: str = field(default_factory=lambda: os.getenv("DXA_PERSONA_KEY", "dxa").strip() or "dxa")
    friends_persona_key: str = field(
        default_factory=lambda: os.getenv("FRIENDS_PERSONA_KEY", "friends").strip() or "friends"
    )
    friends_chat_data_paths: list[Path] = field(
        default_factory=lambda: _split_path_csv(
            os.getenv(
                "FRIENDS_CHAT_DATA_PATHS",
                "data/lxq_chat_data.json,data/Yucheng_Wang_chat_data.json,data/电源_chat_data.json.json",
            )
        )
    )
    friends_user_sender_candidates: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("FRIENDS_USER_SENDER_CANDIDATES", "lxq,Yucheng Wang,电源")
        )
    )
    strict_nickname: str = field(default_factory=lambda: os.getenv("STRICT_NICKNAME", "宝贝"))
    forbidden_nicknames: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("FORBIDDEN_NICKNAMES", "亲亲,宝宝,老婆,老公,宝子,乖乖")
        )
    )
    friends_strict_nickname: str = field(
        default_factory=lambda: os.getenv("FRIENDS_STRICT_NICKNAME", "").strip()
    )
    friends_forbidden_nicknames: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("FRIENDS_FORBIDDEN_NICKNAMES", "宝贝,宝宝,老婆,老公,亲亲,宝子,乖乖")
        )
    )
    app_timezone: str = field(default_factory=lambda: os.getenv("APP_TIMEZONE", "Asia/Shanghai").strip())
    temporal_ack_cooldown_seconds: int = field(
        default_factory=lambda: int(os.getenv("TEMPORAL_ACK_COOLDOWN_SECONDS", str(24 * 3600)))
    )
    temporal_gap_recent_seconds: int = field(
        default_factory=lambda: int(os.getenv("TEMPORAL_GAP_RECENT_SECONDS", "600"))
    )
    temporal_gap_same_day_seconds: int = field(
        default_factory=lambda: int(os.getenv("TEMPORAL_GAP_SAME_DAY_SECONDS", "21600"))
    )
    temporal_gap_two_days_seconds: int = field(
        default_factory=lambda: int(os.getenv("TEMPORAL_GAP_TWO_DAYS_SECONDS", str(2 * 24 * 3600)))
    )
    temporal_gap_week_seconds: int = field(
        default_factory=lambda: int(os.getenv("TEMPORAL_GAP_WEEK_SECONDS", str(7 * 24 * 3600)))
    )

    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "30")))
    semantic_lexical_pool: int = field(
        default_factory=lambda: int(os.getenv("SEMANTIC_LEXICAL_POOL", "100"))
    )
    semantic_top_segments: int = field(
        default_factory=lambda: int(os.getenv("SEMANTIC_TOP_SEGMENTS", "5"))
    )
    semantic_enabled: bool = field(
        default_factory=lambda: os.getenv("SEMANTIC_ENABLED", "true").lower() == "true"
    )
    generation_candidates: int = field(
        default_factory=lambda: int(os.getenv("GENERATION_CANDIDATES", "12"))
    )
    rerank_top_k: int = field(default_factory=lambda: int(os.getenv("RERANK_TOP_K", "6")))
    online_memory_days: int = field(default_factory=lambda: int(os.getenv("ONLINE_MEMORY_DAYS", "14")))

    # Segmenting and semantic index controls.
    segment_window_before: int = field(default_factory=lambda: int(os.getenv("SEGMENT_WINDOW_BEFORE", "6")))
    segment_window_after: int = field(default_factory=lambda: int(os.getenv("SEGMENT_WINDOW_AFTER", "8")))
    segment_max_lines: int = field(default_factory=lambda: int(os.getenv("SEGMENT_MAX_LINES", "18")))
    embedding_batch_size: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_BATCH_SIZE", "24")))
    semantic_recall_k: int = field(default_factory=lambda: int(os.getenv("SEMANTIC_RECALL_K", "120")))
    semantic_autofill_missing: bool = field(
        default_factory=lambda: os.getenv("SEMANTIC_AUTOFILL_MISSING", "true").lower() == "true"
    )
    semantic_autofill_per_query: int = field(
        default_factory=lambda: int(os.getenv("SEMANTIC_AUTOFILL_PER_QUERY", "36"))
    )
    semantic_use_dense_index: bool = field(
        default_factory=lambda: os.getenv("SEMANTIC_USE_DENSE_INDEX", "true").lower() == "true"
    )
    semantic_index_auto_refresh: bool = field(
        default_factory=lambda: os.getenv("SEMANTIC_INDEX_AUTO_REFRESH", "true").lower() == "true"
    )
    semantic_rebuild_on_start: bool = field(
        default_factory=lambda: os.getenv("SEMANTIC_REBUILD_ON_START", "false").lower() == "true"
    )
    semantic_build_on_start_limit: int = field(
        default_factory=lambda: int(os.getenv("SEMANTIC_BUILD_ON_START_LIMIT", "0"))
    )
    rag_max_segment_chars: int = field(
        default_factory=lambda: int(os.getenv("RAG_MAX_SEGMENT_CHARS", "1200"))
    )
    rag_dynamic_window_enabled: bool = field(
        default_factory=lambda: os.getenv("RAG_DYNAMIC_WINDOW_ENABLED", "true").lower() == "true"
    )
    rag_dynamic_window_extra: int = field(
        default_factory=lambda: int(os.getenv("RAG_DYNAMIC_WINDOW_EXTRA", "4"))
    )

    enable_offtopic_penalty: bool = field(
        default_factory=lambda: os.getenv("ENABLE_OFFTOPIC_PENALTY", "true").lower() == "true"
    )
    enable_repair_pass: bool = field(
        default_factory=lambda: os.getenv("ENABLE_REPAIR_PASS", "true").lower() == "true"
    )
    enable_persona_guard: bool = field(
        default_factory=lambda: os.getenv("ENABLE_PERSONA_GUARD", "true").lower() == "true"
    )
    offtopic_penalty_weight: float = field(
        default_factory=lambda: float(os.getenv("OFFTOPIC_PENALTY_WEIGHT", "0.22"))
    )
    repair_threshold_low: float = field(
        default_factory=lambda: float(os.getenv("REPAIR_THRESHOLD_LOW", "0.32"))
    )
    repair_threshold_mid: float = field(
        default_factory=lambda: float(os.getenv("REPAIR_THRESHOLD_MID", "0.55"))
    )
    repair_threshold_high: float = field(
        default_factory=lambda: float(os.getenv("REPAIR_THRESHOLD_HIGH", "0.76"))
    )
    context_frame_recent_messages: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_FRAME_RECENT_MESSAGES", "8"))
    )
    context_frame_anchor_chars: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_FRAME_ANCHOR_CHARS", "180"))
    )
    persona_guard_penalty_weight: float = field(
        default_factory=lambda: float(os.getenv("PERSONA_GUARD_PENALTY_WEIGHT", "0.12"))
    )
    persona_guard_repair_threshold: float = field(
        default_factory=lambda: float(os.getenv("PERSONA_GUARD_REPAIR_THRESHOLD", "0.6"))
    )
    persona_cache_ttl_sec: int = field(
        default_factory=lambda: int(os.getenv("PERSONA_CACHE_TTL_SEC", "600"))
    )
    persona_candidate_min_samples: int = field(
        default_factory=lambda: int(os.getenv("PERSONA_CANDIDATE_MIN_SAMPLES", "12"))
    )
    persona_candidate_min_phrase_freq: int = field(
        default_factory=lambda: int(os.getenv("PERSONA_CANDIDATE_MIN_PHRASE_FREQ", "2"))
    )
    persona_adaptive_top_phrases_limit: int = field(
        default_factory=lambda: int(os.getenv("PERSONA_ADAPTIVE_TOP_PHRASES_LIMIT", "80"))
    )

    cors_allow_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv(
                "CORS_ALLOW_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
        )
    )
    cors_allow_origin_regex: str = field(
        default_factory=lambda: os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"https://.*\.vercel\.app").strip()
    )


settings = Settings()
