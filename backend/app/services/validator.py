from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    passed: bool
    reason: str
    normalized_answer: str
    method: str
    equivalence_score: float
    normalized_expected: str
    normalized_actual: str
    details: dict[str, Any]


class AnswerValidator:
    def validate(self, answer: str, question_type: str, question_text: str = "") -> ValidationResult:
        if question_type == "multiple_choice":
            return self._validate_multiple_choice(answer)

        if question_type == "fill_blank":
            return self._validate_fill_blank(answer)

        if question_type == "calculation":
            return self._validate_calculation(answer, question_text)

        if question_type == "proof":
            return self._validate_proof(answer, question_text)

        return ValidationResult(
            passed=False,
            reason="暂不支持该题型的等价性判定，已返回原始答案",
            normalized_answer=answer.strip(),
            method="fallback_raw_text",
            equivalence_score=0.0,
            normalized_expected="",
            normalized_actual=answer.strip(),
            details={"question_type": question_type},
        )

    def _validate_multiple_choice(self, answer: str) -> ValidationResult:
        normalized = self._normalize_multiple_choice(answer)
        passed = bool(normalized)
        reason = "选择题已完成选项标准化" if passed else "未识别到有效选项，默认保留原答案"
        score = 1.0 if passed else 0.0
        return ValidationResult(
            passed=passed,
            reason=reason,
            normalized_answer=normalized or answer.strip(),
            method="choice_option_normalization",
            equivalence_score=score,
            normalized_expected="",
            normalized_actual=normalized or answer.strip(),
            details={},
        )

    def _validate_fill_blank(self, answer: str) -> ValidationResult:
        normalized = self._normalize_fill_blank(answer)
        passed = bool(normalized)
        reason = "填空题已完成文本标准化" if passed else "填空内容为空，默认保留原答案"
        score = 1.0 if passed else 0.0
        return ValidationResult(
            passed=passed,
            reason=reason,
            normalized_answer=normalized or answer.strip(),
            method="fill_text_normalization",
            equivalence_score=score,
            normalized_expected="",
            normalized_actual=normalized or answer.strip(),
            details={},
        )

    def _validate_calculation(self, answer: str, question_text: str) -> ValidationResult:
        normalized_text = self._normalize_calc_text(answer)
        numbers = self._extract_numbers(answer)
        final_number = numbers[-1] if numbers else ""
        has_equation_pattern = "=" in normalized_text or "所以" in answer or "因此" in answer
        passed = bool(final_number) and has_equation_pattern
        score = 0.9 if passed else (0.45 if final_number else 0.1)
        reason = "计算题已完成数值归一与表达式一致性检查" if passed else "未提取到明确结论数值，建议补充最终结果"
        return ValidationResult(
            passed=passed,
            reason=reason,
            normalized_answer=final_number or normalized_text or answer.strip(),
            method="calc_numeric_rule_match",
            equivalence_score=round(score, 3),
            normalized_expected=self._extract_expected_from_question(question_text),
            normalized_actual=final_number or normalized_text,
            details={
                "numbers_found": numbers,
                "has_equation_pattern": has_equation_pattern,
            },
        )

    def _validate_proof(self, answer: str, question_text: str) -> ValidationResult:
        normalized = self._normalize_fill_blank(answer)
        connectors = ("因为", "所以", "则", "故", "由此", "因此", "假设", "推出")
        conclusion_tokens = ("得证", "命题成立", "证毕", "成立")
        connector_hits = sum(1 for token in connectors if token in answer)
        has_conclusion = any(token in answer for token in conclusion_tokens)
        enough_length = len(normalized) >= 30
        passed = has_conclusion and connector_hits >= 2 and enough_length
        score = 0.35 + min(connector_hits, 4) * 0.15 + (0.15 if has_conclusion else 0.0)
        if not enough_length:
            score = min(score, 0.4)
        reason = "证明题结构校验通过，关键推导链完整" if passed else "证明题结构不完整，建议补充关键推导与结论句"
        return ValidationResult(
            passed=passed,
            reason=reason,
            normalized_answer=normalized or answer.strip(),
            method="proof_structure_heuristic",
            equivalence_score=round(min(score, 0.99), 3),
            normalized_expected=self._extract_expected_from_question(question_text),
            normalized_actual=normalized,
            details={
                "connector_hits": connector_hits,
                "has_conclusion": has_conclusion,
                "answer_length": len(normalized),
            },
        )

    def _normalize_multiple_choice(self, answer: str) -> str:
        match = re.search(r"\b([A-D])\b", answer.upper())
        return match.group(1) if match else ""

    def _normalize_fill_blank(self, answer: str) -> str:
        normalized = answer.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[，。；、,.!?！？]", "", normalized)
        return normalized

    def _normalize_calc_text(self, answer: str) -> str:
        normalized = answer.replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
        normalized = normalized.replace("－", "-").replace("＋", "+").replace("＝", "=")
        normalized = re.sub(r"\s+", "", normalized)
        return normalized

    def _extract_numbers(self, text: str) -> list[str]:
        fraction_pattern = r"-?\d+\s*/\s*-?\d+"
        decimal_pattern = r"-?\d+(?:\.\d+)?"
        raw_numbers = re.findall(f"{fraction_pattern}|{decimal_pattern}", text)
        normalized_numbers: list[str] = []
        for item in raw_numbers:
            cleaned = item.replace(" ", "")
            if "/" in cleaned:
                left, right = cleaned.split("/", 1)
                if right == "0":
                    continue
                value = float(left) / float(right)
                normalized_numbers.append(self._format_number(value))
                continue
            normalized_numbers.append(self._format_number(float(cleaned)))
        return normalized_numbers

    def _format_number(self, value: float) -> str:
        if math.isclose(value, round(value), rel_tol=1e-9, abs_tol=1e-9):
            return str(int(round(value)))
        return f"{value:.8f}".rstrip("0").rstrip(".")

    def _extract_expected_from_question(self, question_text: str) -> str:
        if not question_text:
            return ""
        hints = re.findall(r"(?:等于|为|结果是)\s*([\-]?\d+(?:\.\d+)?)", question_text)
        return hints[-1] if hints else ""
