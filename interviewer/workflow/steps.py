from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from interviewer.core.models import InterviewRuntime, new_id


@dataclass
class WorkflowStepTrace:
    workflow: str
    step: str
    state_before: str | None
    state_after: str | None
    details: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'workflow': self.workflow,
            'step': self.step,
            'state_before': self.state_before,
            'state_after': self.state_after,
            'details': self.details,
            'timestamp': self.timestamp,
        }


class WorkflowStepRecorder:
    def __init__(self) -> None:
        self._traces: list[WorkflowStepTrace] = []

    def record(self, workflow: str, step: str, *, state_before: str | None, state_after: str | None, **details: Any) -> None:
        self._traces.append(
            WorkflowStepTrace(
                workflow=workflow,
                step=step,
                state_before=state_before,
                state_after=state_after,
                details=details,
                timestamp=datetime.now().astimezone().isoformat(),
            )
        )

    def consume(self) -> list[dict[str, Any]]:
        rows = [t.to_dict() for t in self._traces]
        self._traces = []
        return rows


class InterviewStepHandlers:
    def __init__(self, runner: Any) -> None:
        self.runner = runner

    def build_initial_queue(self, runtime: InterviewRuntime, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        queue_seed = self.runner.retrieval.select_initial_questions(
            jd_id=candidate['jd_id'],
            resume_file=candidate['resume_file'],
            question_distribution=self.runner.defaults['question_distribution'],
            resume_count=self.runner.defaults['initial_resume_question_count'],
        )
        queue = self.runner._build_initial_queue(queue_seed)
        self.runner.step_recorder.record(
            'interview_start',
            'build_initial_queue',
            state_before=runtime.state,
            state_after='INTERVIEW_STARTED',
            candidate_id=runtime.candidate_id,
            queue_size=len(queue),
            question_ids=[q['question_id'] for q in queue],
        )
        return queue

    def select_next_question(self, runtime: InterviewRuntime) -> dict[str, Any] | None:
        pending = [q for q in sorted(runtime.queue, key=lambda x: x['order']) if not q.get('asked')]
        selected = pending[0] if pending else None
        self.runner.step_recorder.record(
            'interview_round',
            'select_next_question',
            state_before=runtime.state,
            state_after='WAITING_FOR_REPLY' if selected else runtime.state,
            pending_count=len(pending),
            selected_question_id=(selected or {}).get('question_id'),
        )
        return selected

    def score_answer(self, runtime: InterviewRuntime, question: dict[str, Any], candidate_message: str) -> dict[str, Any]:
        evidence: list[dict[str, Any]] = []
        if runtime.knowledge_id:
            evidence.extend(self.runner.retrieval.retrieve_domain_evidence(jd_id=runtime.knowledge_id, query=question.get('question', '')))
        if runtime.resume_profile_file:
            evidence.extend(self.runner.retrieval.retrieve_resume_evidence(runtime.resume_profile_file, question.get('question', '')))
        score = self.runner.registry.execute(
            'evaluation.score_answer',
            question=question,
            reply_text=candidate_message,
            candidate_id=runtime.candidate_id or 'unknown',
            started_at=runtime.question_started_at,
            max_question_seconds=runtime.max_question_seconds,
            evidence=evidence,
        )
        self.runner.step_recorder.record(
            'interview_round',
            'score_answer',
            state_before=runtime.state,
            state_after='EVALUATING_REPLY',
            question_id=question.get('question_id'),
            overall=(score.get('score') or {}).get('overall'),
            evidence_count=len(evidence),
            missing_points=(score.get('coverage') or {}).get('missing_points', []),
        )
        return score

    def maybe_followup(self, question: dict[str, Any], reply_text: str, runtime: InterviewRuntime, latest_overall: float) -> dict[str, Any] | None:
        followup = self.runner._maybe_build_followup(
            question,
            reply_text,
            runtime.followup_total_count,
            runtime.followup_chain_count,
            latest_overall,
            question.get('answer_count', 1),
        )
        self.runner.step_recorder.record(
            'interview_round',
            'decide_followup',
            state_before=runtime.state,
            state_after='WAITING_FOR_REPLY' if followup else runtime.state,
            source_question_id=question.get('question_id'),
            created=bool(followup),
            followup_question_id=(followup or {}).get('question_id'),
        )
        return followup

    def generate_case(self, runtime: InterviewRuntime, candidate: dict[str, Any]) -> dict[str, Any]:
        resume_profile = self.runner.retrieval.load_resume_profile(candidate['resume_profile_file'])
        history = [row for row in self.runner.cap.storage.read_jsonl(self.runner.cap.storage.score_records_path) if row['candidate_id'] == runtime.candidate_id]
        weak_topics = self.runner.retrieval.summarize_weak_topics(history)
        jd = self.runner.cap.jd_lookup(candidate['jd_id'])
        case_q = self.runner.registry.execute(
            'case.generate',
            role_name=candidate['interview_role'],
            jd_text=jd['jd_text'],
            resume_profile=resume_profile,
            history=history,
            knowledge_id=candidate.get('jd_id'),
            weak_topics=weak_topics,
        )
        self.runner.step_recorder.record(
            'interview_case',
            'generate_case',
            state_before=runtime.state,
            state_after='WAITING_FOR_REPLY',
            candidate_id=runtime.candidate_id,
            weak_topics=weak_topics,
            question_id=(case_q or {}).get('question_id'),
        )
        return case_q

    def finalize(self, runtime: InterviewRuntime, history: list[dict[str, Any]]) -> dict[str, Any]:
        final_score = round(sum(float((row.get('score') or {}).get('overall') or 0) for row in history) / max(len(history), 1), 2)
        subscores = self.runner._subscores(history)
        self.runner.step_recorder.record(
            'interview_finalize',
            'aggregate_scores',
            state_before=runtime.state,
            state_after='FINAL_EVALUATING',
            candidate_id=runtime.candidate_id,
            history_count=len(history),
            final_score=final_score,
            subscores=subscores,
        )
        return {'final_score': final_score, 'subscores': subscores}


__all__ = ['WorkflowStepRecorder', 'WorkflowStepTrace', 'InterviewStepHandlers']
