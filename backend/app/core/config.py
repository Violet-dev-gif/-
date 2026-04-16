from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# 优先从项目根目录/当前工作目录加载 .env，供 Settings 统一读取
load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_host: str
    app_port: int
    app_debug: bool
    openclaw_base_url: str
    openclaw_api_key: str
    glm_base_url: str
    glm_api_key: str
    deepseek_base_url: str
    deepseek_api_key: str
    minimax_base_url: str
    minimax_api_key: str
    redis_url: str
    mysql_dsn: str
    default_model: str
    fallback_model: str
    model_whitelist: tuple[str, ...]
    model_timeout_seconds: float
    model_max_retry: int
    circuit_break_failures: int
    circuit_break_cooldown_seconds: int
    cache_ttl_seconds: int


def _split_csv(raw: str, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw.strip():
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_whitelist = ("mock-primary", "mock-backup")
    model_whitelist = _split_csv(os.getenv("MODEL_WHITELIST", ""), default_whitelist)
    return Settings(
        app_name=os.getenv("APP_NAME", "EducationClaw"),
        app_env=os.getenv("APP_ENV", "dev"),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        app_debug=os.getenv("APP_DEBUG", "true").lower() in {"1", "true", "yes"},
        openclaw_base_url=os.getenv("OPENCLAW_BASE_URL", "").strip(),
        openclaw_api_key=os.getenv("OPENCLAW_API_KEY", "").strip(),
        glm_base_url=os.getenv("GLM_BASE_URL", "").strip(),
        glm_api_key=os.getenv("GLM_API_KEY", "").strip(),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "").strip(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        minimax_base_url=os.getenv("MINIMAX_BASE_URL", "").strip(),
        minimax_api_key=os.getenv("MINIMAX_API_KEY", "").strip(),
        redis_url=os.getenv("REDIS_URL", "").strip(),
        mysql_dsn=os.getenv("MYSQL_DSN", "sqlite:///./educationclaw_v1.db").strip(),
        default_model=os.getenv("DEFAULT_MODEL", "mock-primary").strip(),
        fallback_model=os.getenv("FALLBACK_MODEL", "mock-backup").strip(),
        model_whitelist=model_whitelist,
        model_timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "20")),
        model_max_retry=int(os.getenv("MODEL_MAX_RETRY", "2")),
        circuit_break_failures=int(os.getenv("CIRCUIT_BREAK_FAILURES", "3")),
        circuit_break_cooldown_seconds=int(os.getenv("CIRCUIT_BREAK_COOLDOWN_SECONDS", "45")),
        cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "1800")),
    )
