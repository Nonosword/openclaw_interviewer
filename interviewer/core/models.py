from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
import uuid

QuestionSource = Literal["domain", "resume", "followup", "case"]
RuntimeState = Literal[
    "WAITING_FOR_TIME",
    "WAITING_FOR_IDENTITY",
    "CANDIDATE_IDENTIFIED",
    "INTERVIEW_STARTED",
    "WAITING_FOR_REPLY",
    "EVALUATING_REPLY",
    "CASE_READY",
    "FINAL_EVALUATING",
    "COMPLETED",
]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class DomainKnowledgeItem:
    jd_id: str
    jd_role: str
    topic: str
    subtopic: str
    difficulty: str
    keywords: list[str]
    ideal_points: list[str]
    anti_patterns: list[str]
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResumeProfile:
    resume_id: str
    resume_file: str
    candidate_name: str | None
    parsed: dict[str, Any]
    job_fit: dict[str, Any]
    resume_question_bank_ref: str
    evidence_chunks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateRecord:
    candidate_id: str
    candidate_name: str
    interview_role: str
    jd_id: str
    resume_file: str
    scheduled_at: str
    resume_profile_file: str | None = None
    question_bank_id: str | None = None
    timer_id: str | None = None
    status: str = "new"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TimerRecord:
    timer_id: str
    candidate_id: str
    scheduled_at: str
    late_grace_seconds: int
    max_interview_seconds: int
    max_question_seconds: int
    status: str = "scheduled"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewRuntime:
    session_id: str
    state: RuntimeState
    candidate_id: str | None = None
    candidate_name: str | None = None
    knowledge_id: str | None = None
    resume_profile_file: str | None = None
    queue: list[dict[str, Any]] = field(default_factory=list)
    current_question_id: str | None = None
    followup_total_count: int = 0
    followup_chain_count: int = 0
    interview_started_at: str | None = None
    question_started_at: str | None = None
    scheduled_at: str | None = None
    is_late: bool = False
    max_interview_seconds: int = 3600
    max_question_seconds: int = 300
    asked_question_ids: list[str] = field(default_factory=list)
    completed_case: bool = False
    case_question_count: int = 0
    plan_summary: dict[str, Any] = field(default_factory=dict)
    event_cursor: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
