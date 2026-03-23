from __future__ import annotations

from datetime import datetime
import re
from typing import Any


class Evaluator:
    def score(self, question: dict[str, Any], reply_text: str, candidate_id: str, started_at: str | None, max_question_seconds: int, evidence: list[dict[str, Any]] | None = None, received_at: str | None = None) -> dict[str, Any]:
        reply_text = (reply_text or "").strip()
        received_at = received_at or datetime.now().astimezone().isoformat()
        matched, missing = self._coverage(question.get("ideal_answer_points", []), reply_text)
        coverage_ratio = len(matched) / max(len(question.get("ideal_answer_points", [])), 1)
        has_structure = any(t in reply_text for t in ["首先", "然后", "最后", "第一", "第二", "背景", "验证", "优先", "阶段"])
        has_case = any(t in reply_text for t in ["例如", "比如", "线上", "日志", "监控", "指标", "回滚", "压测", "报警", "复盘"])
        evidence_ratio = self._evidence_ratio(reply_text, evidence or [])
        response_seconds = None
        time_penalty = 0.0
        if started_at:
            try:
                response_seconds = int((datetime.fromisoformat(received_at) - datetime.fromisoformat(started_at)).total_seconds())
            except Exception:
                response_seconds = None
        if response_seconds is not None and response_seconds > max_question_seconds:
            time_penalty = min(1.5, (response_seconds - max_question_seconds) / max_question_seconds * 2)
        fluency = max(0.0, min(10.0, round(5.2 + len(reply_text) / 120 + (0.9 if has_structure else 0) - time_penalty, 2)))
        expression = max(0.0, min(10.0, round(5.0 + len(reply_text) / 130 + (1.0 if has_structure else 0) - time_penalty, 2)))
        knowledge = max(0.0, min(10.0, round(4.2 + coverage_ratio * 4.8 + evidence_ratio * 1.0, 2)))
        core = max(0.0, min(10.0, round(4.2 + coverage_ratio * 3.6 + (1.4 if has_case else 0) + evidence_ratio * 0.8, 2)))
        case = max(0.0, min(10.0, round(4.0 + coverage_ratio * 2.8 + (2.0 if has_case else 0) + evidence_ratio * 1.2, 2)))
        overall = round((fluency + expression + knowledge + core + case) / 5, 2)
        return {
            "question_id": question["question_id"],
            "question_text": question.get("question", ""),
            "candidate_id": candidate_id,
            "reply_text": reply_text,
            "timing": {"question_started_at": started_at, "reply_received_at": received_at, "response_seconds": response_seconds, "max_question_seconds": max_question_seconds},
            "coverage": {"matched_points": matched, "missing_points": missing, "coverage_ratio": round(coverage_ratio, 3), "evidence_ratio": evidence_ratio},
            "score": {"fluency": fluency, "expression": expression, "knowledge": knowledge, "core_competency": core, "case_problem_solving": case, "overall": overall},
            "reason": self._build_reason(matched, missing, has_structure, has_case, evidence_ratio, time_penalty),
            "suggestion": self._build_suggestion(missing, has_case, evidence_ratio),
            "source": question["source"],
            "difficulty": question["difficulty"],
            "topic": question["topic"],
            "source_question_id": question.get("source_question_id"),
            "evidence_refs": question.get("evidence_refs", []),
        }

    def _coverage(self, ideal_points: list[str], reply_text: str) -> tuple[list[str], list[str]]:
        matched, missing = [], []
        reply_tokens = set(self._tokens(reply_text))
        for point in ideal_points:
            point_tokens = set(self._tokens(point))
            if point in reply_text or point[:6] in reply_text or (point_tokens and len(point_tokens & reply_tokens) >= max(1, min(2, len(point_tokens)))):
                matched.append(point)
            else:
                missing.append(point)
        return matched, missing

    def _evidence_ratio(self, reply_text: str, evidence: list[dict[str, Any]]) -> float:
        if not evidence:
            return 0.0
        reply_tokens = set(self._tokens(reply_text))
        hits = 0
        for row in evidence:
            ev_tokens = set(self._tokens(" ".join(row.get("keywords", []) + [row.get("text", ""), row.get("subtopic", ""), row.get("topic", "")])) )
            if reply_tokens & ev_tokens:
                hits += 1
        return round(hits / max(len(evidence), 1), 3)

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-z][A-Za-z0-9_+.-]*|[一-鿿]{2,}", text or "")

    def _build_reason(self, matched: list[str], missing: list[str], has_structure: bool, has_case: bool, evidence_ratio: float, time_penalty: float) -> str:
        parts = ["回答结构清晰。" if has_structure else "回答结构性一般。", f"命中关键点 {len(matched)} 个。"]
        if missing:
            parts.append(f"缺少 {len(missing)} 个关键点。")
        parts.append("包含工程案例或证据。" if has_case else "工程案例或证据偏少。")
        if evidence_ratio > 0:
            parts.append(f"与知识证据存在 {round(evidence_ratio * 100)}% 对齐。")
        if time_penalty > 0:
            parts.append("回答超时，对整体表现有一定影响。")
        return "".join(parts)

    def _build_suggestion(self, missing: list[str], has_case: bool, evidence_ratio: float) -> str:
        tips = []
        if missing:
            tips.append("建议补齐机制、风险、边界和验证方式。")
        if not has_case:
            tips.append("建议增加真实案例、日志、指标或回滚策略。")
        if evidence_ratio < 0.25:
            tips.append("建议回答时更贴近岗位/JD/简历中的具体证据。")
        return "".join(tips) or "可以继续提升复杂场景下的取舍表达。"


def score_answer(question: dict[str, Any], reply_text: str, candidate_id: str, started_at: str | None, max_question_seconds: int, evidence: list[dict[str, Any]] | None = None, received_at: str | None = None) -> dict[str, Any]:
    return Evaluator().score(question, reply_text, candidate_id, started_at, max_question_seconds, evidence=evidence, received_at=received_at)
