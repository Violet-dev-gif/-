from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.adapters import ProviderChatAdapter
from app.services.scheduler import ModelScheduler


class AlwaysFailAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def invoke(self, prompt: str, agent_name: str):  # noqa: ANN201
        self.calls += 1
        raise RuntimeError("boom")


def _settings(**overrides) -> Settings:
    base = dict(
        app_name="EducationClaw",
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        app_debug=False,
        openclaw_base_url="",
        openclaw_api_key="",
        glm_base_url="https://glm.example.com",
        glm_api_key="glm-key",
        deepseek_base_url="https://deepseek.example.com",
        deepseek_api_key="deepseek-key",
        kimi_base_url="https://kimi.example.com",
        kimi_api_key="kimi-key",
        minimax_base_url="https://minimax.example.com",
        minimax_api_key="minimax-key",
        redis_url="",
        mysql_dsn="sqlite:///./test.db",
        default_model="DeepSeek-V3.2",
        fallback_model="DeepSeek-V3.2",
        model_whitelist=("DeepSeek-V3.2",),
        model_timeout_seconds=5.0,
        model_max_retry=0,
        circuit_break_failures=0,
        circuit_break_cooldown_seconds=20,
        cache_ttl_seconds=60,
    )
    base.update(overrides)
    return Settings(**base)


def test_scheduler_maps_deepseek_to_provider_adapter() -> None:
    scheduler = ModelScheduler(_settings())
    adapter = scheduler.adapters["DeepSeek-V3.2"]

    assert isinstance(adapter, ProviderChatAdapter)
    assert adapter.provider_name == "DEEPSEEK"


@pytest.mark.asyncio
async def test_scheduler_stops_retry_when_circuit_opens() -> None:
    scheduler = ModelScheduler(_settings())
    fail_adapter = AlwaysFailAdapter()
    scheduler.adapters["DeepSeek-V3.2"] = fail_adapter

    with pytest.raises(RuntimeError, match="模型调用失败"):
        await scheduler.call_with_policy(prompt="q", agent_name="solve")

    assert fail_adapter.calls == 1
