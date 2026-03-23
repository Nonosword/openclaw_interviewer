from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class AgentWorkspaceConfig:
    candidate: str = '.agent/candidate'
    admin: str = '.agent/admin'
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class WorkerConfig:
    agent_id: str = 'default'
    thinking: str = 'medium'
    timeout_seconds: int = 180
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class SubagentsConfig:
    dialog_parser: WorkerConfig = field(default_factory=WorkerConfig)
    domain_builder: WorkerConfig = field(default_factory=WorkerConfig)
    resume_parser: WorkerConfig = field(default_factory=WorkerConfig)
    question_generator: WorkerConfig = field(default_factory=WorkerConfig)
    evaluator: WorkerConfig = field(default_factory=WorkerConfig)
    case_builder: WorkerConfig = field(default_factory=WorkerConfig)
    def to_dict(self) -> dict[str, Any]:
        return {
            'dialog_parser': self.dialog_parser.to_dict(),
            'domain_builder': self.domain_builder.to_dict(),
            'resume_parser': self.resume_parser.to_dict(),
            'question_generator': self.question_generator.to_dict(),
            'evaluator': self.evaluator.to_dict(),
            'case_builder': self.case_builder.to_dict(),
        }

@dataclass
class PathsConfig:
    rag_root: str = '.rag'
    workspace_root: str = '.workspace'
    workflows_root: str = 'workflows'
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class DefaultsConfig:
    knowledge_prefix: str = 'knowledge'
    initial_domain_question_count: int = 4
    initial_resume_question_count: int = 2
    max_followups_total: int = 5
    max_followups_chain: int = 2
    max_interview_seconds: int = 3600
    max_question_seconds: int = 300
    late_grace_seconds: int = 0
    question_distribution: dict[str, int] = field(default_factory=lambda: {'easy': 1, 'medium': 2, 'hard': 1})
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class SkillConfig:
    agent_workspaces: AgentWorkspaceConfig = field(default_factory=AgentWorkspaceConfig)
    subagents: SubagentsConfig = field(default_factory=SubagentsConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    def to_dict(self) -> dict[str, Any]:
        return {'agent_workspaces': self.agent_workspaces.to_dict(), 'subagents': self.subagents.to_dict(), 'paths': self.paths.to_dict(), 'defaults': self.defaults.to_dict()}
