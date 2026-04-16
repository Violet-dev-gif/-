from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.config import Settings
from app.services.adapters import AdapterResponse, MockModelAdapter, OpenClawAdapter, ProviderChatAdapter


@dataclass
class SchedulerResult:
    model_name: str
    response: AdapterResponse
    attempts: int


@dataclass
class CircuitState:
    fail_count: int = 0
    opened_until: float = 0.0


class ModelScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.max_retry = max(1, settings.model_max_retry)
        self.break_failures = max(1, settings.circuit_break_failures)
        self.break_cooldown_seconds = max(1, settings.circuit_break_cooldown_seconds)
        self.adapters = {}
        self.circuit_state: dict[str, CircuitState] = {}
        self._init_adapters()

    def _init_adapters(self) -> None:
        for model_name in self.settings.model_whitelist:
            self.adapters[model_name] = self._build_adapter(model_name)
            self.circuit_state[model_name] = CircuitState()

        if self.settings.default_model not in self.adapters:
            self.adapters[self.settings.default_model] = self._build_adapter(self.settings.default_model)
            self.circuit_state[self.settings.default_model] = CircuitState()
        if self.settings.fallback_model not in self.adapters:
            self.adapters[self.settings.fallback_model] = self._build_adapter(self.settings.fallback_model)
            self.circuit_state[self.settings.fallback_model] = CircuitState()

    def _build_adapter(self, model_name: str):
        lowered = model_name.lower()
        if lowered.startswith("mock"):
            return MockModelAdapter(model_name=model_name, settings=self.settings)
        if lowered.startswith("glm"):
            return ProviderChatAdapter(
                model_name=model_name,
                settings=self.settings,
                provider_name="GLM",
                base_url=self.settings.glm_base_url,
                api_key=self.settings.glm_api_key,
            )
        if lowered.startswith("deepseek"):
            return ProviderChatAdapter(
                model_name=model_name,
                settings=self.settings,
                provider_name="DEEPSEEK",
                base_url=self.settings.deepseek_base_url,
                api_key=self.settings.deepseek_api_key,
            )
        if lowered.startswith("minimax") or lowered.startswith("abab"):
            return ProviderChatAdapter(
                model_name=model_name,
                settings=self.settings,
                provider_name="MINIMAX",
                base_url=self.settings.minimax_base_url,
                api_key=self.settings.minimax_api_key,
            )
        return OpenClawAdapter(model_name=model_name, settings=self.settings)

    def _is_circuit_open(self, model_name: str) -> bool:
        state = self.circuit_state[model_name]
        return state.opened_until > time.time()

    def _mark_success(self, model_name: str) -> None:
        state = self.circuit_state[model_name]
        state.fail_count = 0
        state.opened_until = 0.0

    def _mark_failure(self, model_name: str) -> None:
        state = self.circuit_state[model_name]
        state.fail_count += 1
        if state.fail_count >= self.break_failures:
            state.opened_until = time.time() + self.break_cooldown_seconds

    def _candidate_models(self, preferred: str | None = None) -> list[str]:
        ordered: list[str] = []
        if preferred and preferred in self.adapters:
            ordered.append(preferred)
        if self.settings.default_model in self.adapters and self.settings.default_model not in ordered:
            ordered.append(self.settings.default_model)
        for model_name in self.settings.model_whitelist:
            if model_name in self.adapters and model_name not in ordered:
                ordered.append(model_name)
        if self.settings.fallback_model in self.adapters and self.settings.fallback_model not in ordered:
            ordered.append(self.settings.fallback_model)
        return ordered

    async def call_with_policy(self, prompt: str, agent_name: str, preferred_model: str | None = None) -> SchedulerResult:
        candidates = self._candidate_models(preferred_model)
        last_error: Exception | None = None
        attempts = 0

        for model_name in candidates:
            if self._is_circuit_open(model_name):
                continue
            adapter = self.adapters[model_name]
            for _ in range(self.max_retry):
                attempts += 1
                try:
                    response = await adapter.invoke(prompt=prompt, agent_name=agent_name)
                    self._mark_success(model_name)
                    return SchedulerResult(model_name=model_name, response=response, attempts=attempts)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    self._mark_failure(model_name)
                    if self._is_circuit_open(model_name):
                        break

        if last_error:
            raise RuntimeError(f"模型调用失败: {last_error}") from last_error
        raise RuntimeError("没有可用模型")

    def list_models(self) -> list[dict]:
        result = []
        for idx, model_name in enumerate(self._candidate_models()):
            status = "open" if self._is_circuit_open(model_name) else "healthy"
            result.append(
                {
                    "model_name": model_name,
                    "status": status,
                    "priority": idx + 1,
                    "is_default": model_name == self.settings.default_model,
                }
            )
        return result
