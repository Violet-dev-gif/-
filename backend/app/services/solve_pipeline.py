from __future__ import annotations

import hashlib
import time
import uuid

from app.schemas import AgentOutputPayload, SolveRequest, SolveResponse, ValidationPayload
from app.services.agents import AgentOrchestrator
from app.services.cache_service import CacheService
from app.services.fusion import VoteFusion
from app.services.persistence import PersistenceService
from app.services.validator import AnswerValidator


class SolvePipeline:
    CACHE_STRATEGY_VERSION = "v2"

    def __init__(
        self,
        *,
        cache_service: CacheService,
        orchestrator: AgentOrchestrator,
        fusion: VoteFusion,
        validator: AnswerValidator,
        persistence: PersistenceService,
    ) -> None:
        self.cache_service = cache_service
        self.orchestrator = orchestrator
        self.fusion = fusion
        self.validator = validator
        self.persistence = persistence

    async def solve(self, request: SolveRequest) -> SolveResponse:
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex
        question_text = request.text.strip()
        question_hash = hashlib.sha256(question_text.encode("utf-8")).hexdigest()
        preferred_model_key = (request.preferred_model or "auto").strip().lower()
        strategy_key = f"{preferred_model_key}:{self.CACHE_STRATEGY_VERSION}"
        strategy_hash = hashlib.sha256(strategy_key.encode("utf-8")).hexdigest()[:12]
        cache_key = f"solve:{question_hash}:{strategy_hash}"

        cached = await self.cache_service.get(cache_key)
        if cached:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.persistence.persist_cache_hit(
                trace_id=trace_id,
                user_id=request.user_id,
                question_hash=question_hash,
                question_text=question_text,
                question_type=cached.get("question_type", "unknown"),
                answer=cached.get("answer", ""),
                normalized_answer=cached.get("normalized_answer", ""),
                confidence=float(cached.get("confidence", 0.0)),
                model_source=cached.get("model_source", "cache"),
                latency_ms=latency_ms,
                token_cost=int(cached.get("token_cost", 0)),
            )
            return SolveResponse(
                trace_id=trace_id,
                cache_hit=True,
                question_type=cached.get("question_type", "unknown"),
                answer=cached.get("answer", ""),
                normalized_answer=cached.get("normalized_answer", ""),
                confidence=float(cached.get("confidence", 0.0)),
                model_source=cached.get("model_source", "cache"),
                latency_ms=latency_ms,
                token_cost=int(cached.get("token_cost", 0)),
                validation=ValidationPayload(
                    passed=bool(cached.get("validation_passed", False)),
                    reason=cached.get("validation_reason", "来自缓存"),
                    normalized_answer=cached.get("normalized_answer", ""),
                    method=cached.get("validation_method", "cache_reuse"),
                    equivalence_score=float(cached.get("validation_equivalence_score", 0.0)),
                    normalized_expected=cached.get("validation_normalized_expected", ""),
                    normalized_actual=cached.get("validation_normalized_actual", cached.get("normalized_answer", "")),
                    details=cached.get("validation_details", {"from_cache": True}),
                ),
                agent_outputs=cached.get("agent_outputs", []),
            )

        parse_output, other_outputs = await self.orchestrator.run_pipeline(
            question=question_text,
            preferred_model=request.preferred_model,
        )
        question_type = str(parse_output.metadata.get("question_type", "unknown"))
        fusion_result = self.fusion.merge(parse_output, other_outputs)
        validation_result = self.validator.validate(fusion_result.answer, question_type, question_text)

        latency_ms = int((time.perf_counter() - started) * 1000)
        all_outputs = [parse_output, *other_outputs]
        self.persistence.persist_solve(
            trace_id=trace_id,
            user_id=request.user_id,
            question_hash=question_hash,
            question_text=question_text,
            question_type=question_type,
            cache_hit=False,
            latency_ms=latency_ms,
            fusion_result=fusion_result,
            validation_result=validation_result,
            agent_outputs=all_outputs,
        )

        agent_payloads = [
            AgentOutputPayload(
                agent_name=output.agent_name,
                answer=output.answer,
                confidence=output.confidence,
                model_name=output.model_name,
                token_cost=output.token_cost,
                metadata=output.metadata,
            )
            for output in all_outputs
        ]

        cached_payload = {
            "question_type": question_type,
            "answer": fusion_result.answer,
            "normalized_answer": validation_result.normalized_answer,
            "confidence": fusion_result.confidence,
            "model_source": fusion_result.model_source,
            "token_cost": fusion_result.token_cost,
            "validation_passed": validation_result.passed,
            "validation_reason": validation_result.reason,
            "validation_method": validation_result.method,
            "validation_equivalence_score": validation_result.equivalence_score,
            "validation_normalized_expected": validation_result.normalized_expected,
            "validation_normalized_actual": validation_result.normalized_actual,
            "validation_details": validation_result.details,
            "agent_outputs": [payload.model_dump() for payload in agent_payloads],
        }
        cache_write_failed = False
        try:
            await self.cache_service.set(cache_key, cached_payload)
        except Exception:  # noqa: BLE001
            cache_write_failed = True

        response = SolveResponse(
            trace_id=trace_id,
            cache_hit=False,
            question_type=question_type,
            answer=fusion_result.answer,
            normalized_answer=validation_result.normalized_answer,
            confidence=fusion_result.confidence,
            model_source=fusion_result.model_source,
            latency_ms=latency_ms,
            token_cost=fusion_result.token_cost,
            validation=ValidationPayload(
                passed=validation_result.passed,
                reason=validation_result.reason,
                normalized_answer=validation_result.normalized_answer,
                method=validation_result.method,
                equivalence_score=validation_result.equivalence_score,
                normalized_expected=validation_result.normalized_expected,
                normalized_actual=validation_result.normalized_actual,
                details=validation_result.details,
            ),
            agent_outputs=agent_payloads,
        )
        if cache_write_failed:
            response.validation.details["cache_write_failed"] = True
        return response
