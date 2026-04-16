from __future__ import annotations

from app.services.agents import AgentOutput
from app.services.fusion import VoteFusion


def _output(agent_name: str, answer: str, confidence: float, model_name: str) -> AgentOutput:
    return AgentOutput(
        agent_name=agent_name,
        answer=answer,
        confidence=confidence,
        model_name=model_name,
        token_cost=10,
        latency_ms=10,
        metadata={},
    )


def test_fusion_prefers_solve_answer_even_if_other_confidence_higher() -> None:
    fusion = VoteFusion()
    parse = _output("parse", "parse text", 0.99, "parse-model")
    retrieve = _output("retrieve", "retrieve text", 0.99, "retrieve-model")
    solve = _output("solve", "final answer from solve", 0.4, "solve-model")
    verify = _output("verify", "verify text", 0.99, "verify-model")

    result = fusion.merge(parse, [retrieve, solve, verify])

    assert result.answer == "final answer from solve"
    assert result.model_source == "solve@solve-model"
    assert result.token_cost == 40


def test_fusion_falls_back_to_best_non_empty_when_solve_missing() -> None:
    fusion = VoteFusion()
    parse = _output("parse", "parse text", 0.5, "parse-model")
    retrieve = _output("retrieve", "retrieve text", 0.95, "retrieve-model")
    solve = _output("solve", "", 0.95, "solve-model")
    verify = _output("verify", "verify text", 0.1, "verify-model")

    result = fusion.merge(parse, [retrieve, solve, verify])

    assert result.answer == "retrieve text"
    assert result.model_source == "retrieve@retrieve-model"
