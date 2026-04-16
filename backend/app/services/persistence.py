from __future__ import annotations

from app.db.database import db_session
from app.db.models import ModelCallLog, SolveRecord, UserProfile
from app.services.agents import AgentOutput
from app.services.fusion import FusionResult
from app.services.validator import ValidationResult


class PersistenceService:
    def persist_solve(
        self,
        *,
        trace_id: str,
        user_id: str | None,
        question_hash: str,
        question_text: str,
        question_type: str,
        cache_hit: bool,
        latency_ms: int,
        fusion_result: FusionResult,
        validation_result: ValidationResult,
        agent_outputs: list[AgentOutput],
    ) -> None:
        with db_session() as session:
            solve_record = SolveRecord(
                trace_id=trace_id,
                user_id=user_id,
                question_hash=question_hash,
                question_text=question_text,
                question_type=question_type,
                final_answer=fusion_result.answer,
                normalized_answer=validation_result.normalized_answer,
                confidence=fusion_result.confidence,
                model_source=fusion_result.model_source,
                latency_ms=latency_ms,
                token_cost=fusion_result.token_cost,
                cache_hit=cache_hit,
            )
            session.add(solve_record)

            for output in agent_outputs:
                excerpt = output.answer[:300]
                session.add(
                    ModelCallLog(
                        trace_id=trace_id,
                        agent_name=output.agent_name,
                        model_name=output.model_name,
                        success=bool(output.answer.strip()),
                        latency_ms=output.latency_ms,
                        token_cost=output.token_cost,
                        response_excerpt=excerpt,
                    )
                )

            self._update_user_profile(session=session, user_id=user_id)

    def persist_cache_hit(
        self,
        *,
        trace_id: str,
        user_id: str | None,
        question_hash: str,
        question_text: str,
        question_type: str,
        answer: str,
        normalized_answer: str,
        confidence: float,
        model_source: str,
        latency_ms: int,
        token_cost: int,
    ) -> None:
        with db_session() as session:
            session.add(
                SolveRecord(
                    trace_id=trace_id,
                    user_id=user_id,
                    question_hash=question_hash,
                    question_text=question_text,
                    question_type=question_type,
                    final_answer=answer,
                    normalized_answer=normalized_answer,
                    confidence=confidence,
                    model_source=model_source,
                    latency_ms=latency_ms,
                    token_cost=token_cost,
                    cache_hit=True,
                )
            )
            session.add(
                ModelCallLog(
                    trace_id=trace_id,
                    agent_name="cache",
                    model_name=model_source,
                    success=bool(answer.strip()),
                    latency_ms=latency_ms,
                    token_cost=token_cost,
                    response_excerpt=answer[:300],
                )
            )
            self._update_user_profile(session=session, user_id=user_id)

    def _update_user_profile(self, *, session, user_id: str | None) -> None:
        if not user_id:
            return
        profile = session.get(UserProfile, user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id, solved_count=1)
            session.add(profile)
        else:
            profile.solved_count += 1
        profile.level = self._compute_level(profile.solved_count)

    @staticmethod
    def _compute_level(solved_count: int) -> int:
        if solved_count >= 500:
            return 3
        if solved_count >= 200:
            return 2
        if solved_count >= 50:
            return 1
        return 0
