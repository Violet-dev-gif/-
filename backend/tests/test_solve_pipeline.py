from __future__ import annotations

import pytest

from app.schemas import SolveRequest
from app.services.agents import AgentOutput
from app.services.fusion import FusionResult
from app.services.solve_pipeline import SolvePipeline
from app.services.validator import ValidationResult


class FakeCacheService:
    def __init__(self, *, cached: dict | None = None, fail_set: bool = False) -> None:
        self.cached = cached
        self.fail_set = fail_set
        self.get_keys: list[str] = []
        self.set_keys: list[str] = []

    async def get(self, key: str) -> dict | None:
        self.get_keys.append(key)
        return self.cached

    async def set(self, key: str, payload: dict, ttl_seconds: int | None = None) -> None:
        self.set_keys.append(key)
        if self.fail_set:
            raise RuntimeError("cache down")


class FakeOrchestrator:
    async def run_pipeline(self, question: str, preferred_model: str | None = None) -> tuple[AgentOutput, list[AgentOutput]]:
        parse = AgentOutput("parse", "parse", 0.8, "parse-model", 10, 10, {"question_type": "calculation"})
        retrieve = AgentOutput("retrieve", "retrieve", 0.7, "retrieve-model", 10, 10, {})
        solve = AgentOutput("solve", "solve-answer", 0.9, "solve-model", 20, 12, {})
        verify = AgentOutput("verify", "verify", 0.8, "verify-model", 10, 8, {})
        return parse, [retrieve, solve, verify]


class FakeFusion:
    def merge(self, parse_output: AgentOutput, other_outputs: list[AgentOutput]) -> FusionResult:
        return FusionResult(
            answer="merged-answer",
            confidence=0.9,
            model_source="solve@solve-model",
            token_cost=40,
        )


class FakeValidator:
    def validate(self, answer: str, question_type: str, question_text: str = "") -> ValidationResult:
        return ValidationResult(
            passed=True,
            reason="ok",
            normalized_answer="42",
            method="test",
            equivalence_score=1.0,
            normalized_expected="42",
            normalized_actual="42",
            details={},
        )


class FakePersistence:
    def __init__(self) -> None:
        self.solve_calls = 0
        self.cache_hit_calls = 0

    def persist_solve(self, **kwargs) -> None:  # noqa: ANN003, ANN201
        self.solve_calls += 1

    def persist_cache_hit(self, **kwargs) -> None:  # noqa: ANN003, ANN201
        self.cache_hit_calls += 1


@pytest.mark.asyncio
async def test_cache_key_isolated_by_preferred_model() -> None:
    cache = FakeCacheService(cached=None)
    persistence = FakePersistence()
    pipeline = SolvePipeline(
        cache_service=cache,
        orchestrator=FakeOrchestrator(),
        fusion=FakeFusion(),
        validator=FakeValidator(),
        persistence=persistence,
    )

    await pipeline.solve(SolveRequest(text="same question", preferred_model="glm-5.1"))
    await pipeline.solve(SolveRequest(text="same question", preferred_model="DeepSeek-V3.2"))

    assert len(cache.get_keys) == 2
    assert cache.get_keys[0] != cache.get_keys[1]


@pytest.mark.asyncio
async def test_cache_hit_writes_audit_record() -> None:
    cache = FakeCacheService(
        cached={
            "question_type": "calculation",
            "answer": "cached-answer",
            "normalized_answer": "42",
            "confidence": 0.88,
            "model_source": "solve@cache-model",
            "token_cost": 10,
            "validation_passed": True,
            "validation_reason": "from-cache",
            "validation_method": "cache_reuse",
            "validation_equivalence_score": 1.0,
            "validation_normalized_expected": "42",
            "validation_normalized_actual": "42",
            "validation_details": {"from_cache": True},
            "agent_outputs": [],
        }
    )
    persistence = FakePersistence()
    pipeline = SolvePipeline(
        cache_service=cache,
        orchestrator=FakeOrchestrator(),
        fusion=FakeFusion(),
        validator=FakeValidator(),
        persistence=persistence,
    )

    response = await pipeline.solve(SolveRequest(text="same question", user_id="u-1"))

    assert response.cache_hit is True
    assert persistence.cache_hit_calls == 1
    assert persistence.solve_calls == 0


@pytest.mark.asyncio
async def test_cache_set_failure_does_not_fail_main_response() -> None:
    cache = FakeCacheService(cached=None, fail_set=True)
    persistence = FakePersistence()
    pipeline = SolvePipeline(
        cache_service=cache,
        orchestrator=FakeOrchestrator(),
        fusion=FakeFusion(),
        validator=FakeValidator(),
        persistence=persistence,
    )

    response = await pipeline.solve(SolveRequest(text="question"))

    assert response.cache_hit is False
    assert response.validation.details.get("cache_write_failed") is True
    assert persistence.solve_calls == 1
