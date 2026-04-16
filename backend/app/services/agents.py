from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.retrieval import RetrievalService
from app.services.scheduler import ModelScheduler


@dataclass
class AgentOutput:
    agent_name: str
    answer: str
    confidence: float
    model_name: str
    token_cost: int
    latency_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    def __init__(self, scheduler: ModelScheduler, retrieval_service: RetrievalService) -> None:
        self.scheduler = scheduler
        self.retrieval_service = retrieval_service

    async def run_parse(self, question: str, preferred_model: str | None = None) -> AgentOutput:
        prompt = f"请解析题目，识别题型与关键信息:\n{question}"
        result = await self.scheduler.call_with_policy(prompt=prompt, agent_name="parse", preferred_model=preferred_model)
        question_type = self._detect_question_type(question)
        return AgentOutput(
            agent_name="parse",
            answer=result.response.answer,
            confidence=result.response.confidence,
            model_name=result.model_name,
            token_cost=result.response.token_cost,
            latency_ms=result.response.latency_ms,
            metadata={"question_type": question_type},
        )

    async def run_retrieve(self, question: str, preferred_model: str | None = None) -> AgentOutput:
        retrieved = await self.retrieval_service.search(question)
        hint = "\n".join(retrieved[:3]) if retrieved else "暂无向量检索结果"
        prompt = f"根据题目和检索提示给出相关知识点:\n题目:{question}\n检索:{hint}"
        result = await self.scheduler.call_with_policy(prompt=prompt, agent_name="retrieve", preferred_model=preferred_model)
        return AgentOutput(
            agent_name="retrieve",
            answer=result.response.answer,
            confidence=result.response.confidence,
            model_name=result.model_name,
            token_cost=result.response.token_cost,
            latency_ms=result.response.latency_ms,
            metadata={"retrieved_count": len(retrieved)},
        )

    async def run_solve(self, question: str, preferred_model: str | None = None) -> AgentOutput:
        prompt = (
            "你是一名严谨的解题助手，请按如下格式作答：\n"
            "1、先给出必要的推理与步骤；\n"
            "2、最后单独一行写出“最终答案：XXX”，其中 XXX 为本题的最终数值或结论。\n"
            f"题目：{question}"
        )
        result = await self.scheduler.call_with_policy(prompt=prompt, agent_name="solve", preferred_model=preferred_model)
        return AgentOutput(
            agent_name="solve",
            answer=result.response.answer,
            confidence=result.response.confidence,
            model_name=result.model_name,
            token_cost=result.response.token_cost,
            latency_ms=result.response.latency_ms,
            metadata={},
        )

    async def run_verify(self, question: str, candidate_answer: str, preferred_model: str | None = None) -> AgentOutput:
        prompt = (
            "请从严校验下列候选答案是否正确，自洽，并指出潜在风险点。\n"
            "1、如果最终数值或结论明显错误，请说明正确答案应为多少；\n"
            "2、如果步骤正确但表达不清，请说明需要改进之处；\n"
            f"题目：{question}\n候选答案：{candidate_answer}"
        )
        result = await self.scheduler.call_with_policy(prompt=prompt, agent_name="verify", preferred_model=preferred_model)
        return AgentOutput(
            agent_name="verify",
            answer=result.response.answer,
            confidence=result.response.confidence,
            model_name=result.model_name,
            token_cost=result.response.token_cost,
            latency_ms=result.response.latency_ms,
            metadata={},
        )

    async def run_pipeline(self, question: str, preferred_model: str | None = None) -> tuple[AgentOutput, list[AgentOutput]]:
        parse_output = await self.run_parse(question, preferred_model=preferred_model)
        retrieve_task = self.run_retrieve(question, preferred_model=preferred_model)
        solve_task = self.run_solve(question, preferred_model=preferred_model)
        retrieve_result, solve_result = await asyncio.gather(retrieve_task, solve_task, return_exceptions=True)

        if isinstance(solve_result, Exception):
            raise RuntimeError(f"solve agent failed: {solve_result}") from solve_result
        solve_output = solve_result

        if isinstance(retrieve_result, Exception):
            retrieve_output = self._error_output("retrieve", retrieve_result)
        else:
            retrieve_output = retrieve_result

        try:
            verify_output = await self.run_verify(
                question,
                candidate_answer=solve_output.answer,
                preferred_model=preferred_model,
            )
        except Exception as exc:  # noqa: BLE001
            verify_output = self._error_output("verify", exc)

        return parse_output, [retrieve_output, solve_output, verify_output]

    def _error_output(self, agent_name: str, error: Exception) -> AgentOutput:
        return AgentOutput(
            agent_name=agent_name,
            answer="",
            confidence=0.0,
            model_name="error",
            token_cost=0,
            latency_ms=0,
            metadata={"error": str(error)},
        )

    def _detect_question_type(self, question: str) -> str:
        text = question.strip()
        if re.search(r"[A-D][\.\、\)]", text):
            return "multiple_choice"
        if "填空" in text or "____" in text or "__" in text:
            return "fill_blank"
        calculation_keywords = ("计算", "求值", "解方程", "化简", "求导", "积分", "证明数值", "求")
        if any(keyword in text for keyword in calculation_keywords) or re.search(r"[=+\-*/^]", text):
            return "calculation"
        proof_keywords = ("证明", "请证", "论证", "说明理由", "推导")
        if any(keyword in text for keyword in proof_keywords):
            return "proof"
        return "unknown"
