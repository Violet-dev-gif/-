from __future__ import annotations

from dataclasses import dataclass

from app.services.agents import AgentOutput


@dataclass
class FusionResult:
    answer: str
    confidence: float
    model_source: str
    token_cost: int


class VoteFusion:
    def __init__(self) -> None:
        self.weights = {
            "parse": 0.15,
            "retrieve": 0.15,
            "solve": 0.5,
            "verify": 0.2,
        }

    def merge(self, parse_output: AgentOutput, other_outputs: list[AgentOutput]) -> FusionResult:
        outputs = [parse_output, *other_outputs]
        weighted_sum = 0.0
        token_cost = 0
        best_answer = ""
        best_score = -1.0
        best_model = ""
        best_agent = "unknown"
        solve_output = next((output for output in outputs if output.agent_name == "solve"), None)

        for output in outputs:
            weight = self.weights.get(output.agent_name, 0.1)
            score = weight * max(0.0, min(output.confidence, 1.0))
            weighted_sum += score
            token_cost += output.token_cost
            if score > best_score and output.answer.strip():
                best_score = score
                best_answer = output.answer
                best_model = output.model_name
                best_agent = output.agent_name

        confidence = max(0.0, min(weighted_sum, 0.99))
        if solve_output and solve_output.answer.strip():
            final_answer = solve_output.answer
            model_source = f"solve@{solve_output.model_name}"
        else:
            final_answer = best_answer
            model_source = f"{best_agent}@{best_model}" if best_model else "unknown"

        return FusionResult(
            answer=final_answer,
            confidence=confidence,
            model_source=model_source,
            token_cost=token_cost,
        )
