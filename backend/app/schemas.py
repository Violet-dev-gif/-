from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SolveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    user_id: str | None = None
    preferred_model: str | None = None


class ValidationPayload(BaseModel):
    passed: bool
    reason: str
    normalized_answer: str
    method: str = ""
    equivalence_score: float = 0.0
    normalized_expected: str = ""
    normalized_actual: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class AgentOutputPayload(BaseModel):
    agent_name: str
    answer: str
    confidence: float
    model_name: str
    token_cost: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class SolveResponse(BaseModel):
    trace_id: str
    cache_hit: bool
    question_type: str
    answer: str
    normalized_answer: str
    confidence: float
    model_source: str
    latency_ms: int
    token_cost: int
    validation: ValidationPayload
    agent_outputs: list[AgentOutputPayload]


class ModelInfoResponse(BaseModel):
    model_name: str
    status: str
    priority: int
    is_default: bool


class HealthResponse(BaseModel):
    app: str
    env: str
    status: str
    redis_connected: bool
    db_ready: bool
