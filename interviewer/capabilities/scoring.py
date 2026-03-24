from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from interviewer.config.loader import load_config
from interviewer.subagents.dispatcher import LocalSubagentDispatcher


class Evaluator:
    def __init__(self, root: str | Path | None = None, dispatcher: LocalSubagentDispatcher | None = None):
        self.root = Path(root) if root is not None else None
        self.dispatcher = dispatcher

    def score(
        self,
        question: dict[str, Any],
        reply_text: str,
        candidate_id: str,
        started_at: str | None,
        max_question_seconds: int,
        *,
        role_name: str,
        jd_text: str,
        resume_profile: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        history: list[dict[str, Any]] | None = None,
        received_at: str | None = None,
    ) -> dict[str, Any]:
        reply_text = '' if reply_text is None else str(reply_text)
        normalized_reply_text = reply_text.strip()
        received_at = received_at or datetime.now().astimezone().isoformat()
        response_seconds = None
        if started_at:
            try:
                response_seconds = int((datetime.fromisoformat(received_at) - datetime.fromisoformat(started_at)).total_seconds())
            except Exception:
                response_seconds = None
        dispatcher = self._dispatcher()
        evaluated = dispatcher.evaluate_answer(
            question=question,
            reply_text=reply_text,
            candidate_id=candidate_id,
            role_name=role_name,
            jd_text=jd_text,
            resume_profile=resume_profile,
            evidence=evidence or [],
            history=history or [],
            started_at=started_at,
            received_at=received_at,
            response_seconds=response_seconds,
            max_question_seconds=max_question_seconds,
        )
        evaluated = self._apply_time_penalty(
            evaluated=evaluated,
            response_seconds=response_seconds,
            max_question_seconds=max_question_seconds,
        )
        return {
            'question_id': question['question_id'],
            'question_text': question.get('question', ''),
            'candidate_id': candidate_id,
            'reply_text': reply_text,
            'normalized_reply_text': normalized_reply_text,
            'timing': {
                'question_started_at': started_at,
                'reply_received_at': received_at,
                'response_seconds': response_seconds,
                'max_question_seconds': max_question_seconds,
            },
            'coverage': evaluated['coverage'],
            'score': evaluated['score'],
            'reason': str(evaluated.get('reason') or ''),
            'suggestion': str(evaluated.get('suggestion') or ''),
            'source': question['source'],
            'difficulty': question['difficulty'],
            'topic': question['topic'],
            'source_question_id': question.get('source_question_id'),
            'evidence_refs': question.get('evidence_refs', []),
        }

    def _dispatcher(self) -> LocalSubagentDispatcher:
        if self.dispatcher is not None:
            return self.dispatcher
        cfg = load_config(self.root or Path.cwd())
        self.dispatcher = LocalSubagentDispatcher(self.root, cfg.subagents)
        return self.dispatcher

    def _apply_time_penalty(
        self,
        *,
        evaluated: dict[str, Any],
        response_seconds: int | None,
        max_question_seconds: int,
    ) -> dict[str, Any]:
        if response_seconds is None or max_question_seconds <= 0 or response_seconds <= max_question_seconds:
            return evaluated
        penalty = min(1.5, (response_seconds - max_question_seconds) / max_question_seconds * 2)
        score = dict(evaluated.get('score') or {})
        for key in ('fluency', 'expression'):
            if key in score:
                score[key] = round(max(0.0, min(10.0, float(score.get(key) or 0) - penalty)), 2)
        numeric_keys = ['fluency', 'expression', 'knowledge', 'core_competency', 'case_problem_solving']
        present = [float(score.get(key) or 0) for key in numeric_keys if key in score]
        if present:
            recomputed_overall = sum(present) / len(present)
            original_overall = float((evaluated.get('score') or {}).get('overall') or 0)
            score['overall'] = round(max(0.0, min(original_overall, recomputed_overall) - penalty * 0.5), 2)
        reason = str(evaluated.get('reason') or '')
        if '超时' not in reason:
            reason = f'{reason}回答超时，对表达与整体表现有一定影响。'.strip()
        updated = dict(evaluated)
        updated['score'] = score
        updated['reason'] = reason
        return updated


def score_answer(
    question: dict[str, Any],
    reply_text: str,
    candidate_id: str,
    started_at: str | None,
    max_question_seconds: int,
    *,
    role_name: str,
    jd_text: str,
    root: str | Path | None = None,
    dispatcher: LocalSubagentDispatcher | None = None,
    resume_profile: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
    received_at: str | None = None,
) -> dict[str, Any]:
    return Evaluator(root=root, dispatcher=dispatcher).score(
        question,
        reply_text,
        candidate_id,
        started_at,
        max_question_seconds,
        role_name=role_name,
        jd_text=jd_text,
        resume_profile=resume_profile,
        evidence=evidence,
        history=history,
        received_at=received_at,
    )
