from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings


@dataclass
class AdapterResponse:
    answer: str
    confidence: float
    token_cost: int
    latency_ms: int
    raw: dict


class BaseModelAdapter:
    def __init__(self, model_name: str, settings: Settings) -> None:
        self.model_name = model_name
        self.settings = settings

    async def invoke(self, prompt: str, agent_name: str) -> AdapterResponse:
        raise NotImplementedError


class MockModelAdapter(BaseModelAdapter):
    async def invoke(self, prompt: str, agent_name: str) -> AdapterResponse:
        started = time.perf_counter()
        digest = hashlib.sha256(f"{self.model_name}:{agent_name}:{prompt}".encode("utf-8")).hexdigest()
        confidence = 0.68 + (int(digest[:2], 16) / 255.0) * 0.28
        answer = self._render_answer(prompt, agent_name, digest)
        latency_ms = int((time.perf_counter() - started) * 1000) + 8
        return AdapterResponse(
            answer=answer,
            confidence=min(confidence, 0.96),
            token_cost=max(32, len(prompt) // 5),
            latency_ms=latency_ms,
            raw={"digest": digest[:12], "provider": "mock"},
        )

    def _render_answer(self, prompt: str, agent_name: str, digest: str) -> str:
        if agent_name == "parse":
            return f"解析要点: 题干长度{len(prompt)}，关键哈希{digest[:6]}"
        if agent_name == "retrieve":
            return f"检索摘要: 暂未命中向量库，建议围绕题干关键词构建同类题"
        if agent_name == "verify":
            return "校验结论: 推导过程结构完整，未发现明显矛盾"
        return f"解题草案: 根据题意可得到候选答案，建议先化简再代入验证。"


class OpenClawAdapter(BaseModelAdapter):
    async def invoke(self, prompt: str, agent_name: str) -> AdapterResponse:
        if not self.settings.openclaw_base_url:
            raise RuntimeError("OPENCLAW_BASE_URL 未配置")

        headers = {"Content-Type": "application/json"}
        if self.settings.openclaw_api_key:
            headers["Authorization"] = f"Bearer {self.settings.openclaw_api_key}"

        payload = {
            "text": prompt,
            "agent": agent_name,
            "model": self.model_name,
        }

        started = time.perf_counter()
        timeout = httpx.Timeout(self.settings.model_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.settings.openclaw_base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        answer = (
            data.get("answer")
            or data.get("response")
            or data.get("content")
            or data.get("text")
            or data.get("message")
            or ""
        )
        if not answer:
            answer = str(data)

        latency_ms = int((time.perf_counter() - started) * 1000)
        token_cost = int(data.get("token_cost", max(64, len(prompt) // 4)))
        confidence = float(data.get("confidence", 0.8))
        return AdapterResponse(
            answer=answer,
            confidence=max(0.0, min(confidence, 0.99)),
            token_cost=token_cost,
            latency_ms=latency_ms,
            raw=data if isinstance(data, dict) else {"raw": str(data)},
        )


class ProviderChatAdapter(BaseModelAdapter):
    def __init__(
        self,
        model_name: str,
        settings: Settings,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
    ) -> None:
        super().__init__(model_name=model_name, settings=settings)
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def invoke(self, prompt: str, agent_name: str) -> AdapterResponse:
        if not self.base_url:
            raise RuntimeError(f"{self.provider_name} BASE_URL 未配置")
        if not self.api_key:
            raise RuntimeError(f"{self.provider_name} API_KEY 未配置")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": f"你是{agent_name} Agent，请保持输出简洁且可验证。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        started = time.perf_counter()
        timeout = httpx.Timeout(self.settings.model_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        answer = self._extract_answer(data)
        if not answer:
            answer = str(data)
        latency_ms = int((time.perf_counter() - started) * 1000)
        token_cost = self._extract_token_cost(data, prompt)
        confidence = float(data.get("confidence", 0.82)) if isinstance(data, dict) else 0.82
        return AdapterResponse(
            answer=answer,
            confidence=max(0.0, min(confidence, 0.99)),
            token_cost=token_cost,
            latency_ms=latency_ms,
            raw={"provider": self.provider_name, "data": data},
        )

    def _extract_answer(self, data: dict | list | str) -> str:
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                if isinstance(message, dict) and message.get("content"):
                    return str(message["content"])
                if choices[0].get("text"):
                    return str(choices[0]["text"])
            for key in ("answer", "response", "content", "text", "message", "reply", "output_text"):
                if data.get(key):
                    return str(data[key])
        return ""

    def _extract_token_cost(self, data: dict | list | str, prompt: str) -> int:
        if isinstance(data, dict):
            usage = data.get("usage", {})
            if isinstance(usage, dict):
                total = usage.get("total_tokens") or usage.get("totalTokens")
                if total is not None:
                    return int(total)
            token_cost = data.get("token_cost")
            if token_cost is not None:
                return int(token_cost)
        return max(64, len(prompt) // 4)
