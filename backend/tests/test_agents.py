from __future__ import annotations

import pytest

from app.services.agents import AgentOrchestrator, AgentOutput


class DummyRetrievalService:
    async def search(self, question: str) -> list[str]:
        return []


def _build_output(agent_name: str, answer: str, confidence: float = 0.9) -> AgentOutput:
    return AgentOutput(
        agent_name=agent_name,
        answer=answer,
        confidence=confidence,
        model_name=f"{agent_name}-model",
        token_cost=10,
        latency_ms=20,
        metadata={},
    )


@pytest.mark.asyncio
async def test_run_pipeline_verify_uses_solve_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = AgentOrchestrator(scheduler=None, retrieval_service=DummyRetrievalService())
    verify_inputs: dict[str, str] = {}

    async def fake_parse(question: str, preferred_model: str | None = None) -> AgentOutput:
        return _build_output("parse", "parse-answer")

    async def fake_retrieve(question: str, preferred_model: str | None = None) -> AgentOutput:
        return _build_output("retrieve", "retrieve-answer")

    async def fake_solve(question: str, preferred_model: str | None = None) -> AgentOutput:
        return _build_output("solve", "solve-answer")

    async def fake_verify(
        question: str,
        candidate_answer: str,
        preferred_model: str | None = None,
    ) -> AgentOutput:
        verify_inputs["candidate_answer"] = candidate_answer
        return _build_output("verify", "verify-answer")

    monkeypatch.setattr(orchestrator, "run_parse", fake_parse)
    monkeypatch.setattr(orchestrator, "run_retrieve", fake_retrieve)
    monkeypatch.setattr(orchestrator, "run_solve", fake_solve)
    monkeypatch.setattr(orchestrator, "run_verify", fake_verify)

    _, outputs = await orchestrator.run_pipeline("question")

    assert verify_inputs["candidate_answer"] == "solve-answer"
    assert [item.agent_name for item in outputs] == ["retrieve", "solve", "verify"]


@pytest.mark.asyncio
async def test_run_pipeline_retrieve_verify_failure_is_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = AgentOrchestrator(scheduler=None, retrieval_service=DummyRetrievalService())

    async def fake_parse(question: str, preferred_model: str | None = None) -> AgentOutput:
        return _build_output("parse", "parse-answer")

    async def fake_retrieve(question: str, preferred_model: str | None = None) -> AgentOutput:
        raise RuntimeError("retrieve failed")

    async def fake_solve(question: str, preferred_model: str | None = None) -> AgentOutput:
        return _build_output("solve", "solve-answer")

    async def fake_verify(
        question: str,
        candidate_answer: str,
        preferred_model: str | None = None,
    ) -> AgentOutput:
        raise RuntimeError("verify failed")

    monkeypatch.setattr(orchestrator, "run_parse", fake_parse)
    monkeypatch.setattr(orchestrator, "run_retrieve", fake_retrieve)
    monkeypatch.setattr(orchestrator, "run_solve", fake_solve)
    monkeypatch.setattr(orchestrator, "run_verify", fake_verify)

    _, outputs = await orchestrator.run_pipeline("question")
    retrieve_output, solve_output, verify_output = outputs

    assert solve_output.answer == "solve-answer"
    assert retrieve_output.model_name == "error"
    assert verify_output.model_name == "error"
    assert "error" in retrieve_output.metadata
    assert "error" in verify_output.metadata
