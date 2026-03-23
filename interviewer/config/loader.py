from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import AgentWorkspaceConfig, DefaultsConfig, PathsConfig, SkillConfig, SubagentsConfig, WorkerConfig
from interviewer.simple_yaml import dump_yaml_text, load_yaml_text

CONFIG_CANDIDATES = ('config.yaml','config.yml','config.json')

def _default_config() -> SkillConfig:
    return SkillConfig()

def discover_config_path(root: str | Path) -> Path:
    base = Path(root)
    for name in CONFIG_CANDIDATES:
        path = base / name
        if path.exists():
            return path
    return base / 'config.yaml'

def config_path(root: str | Path) -> Path:
    return discover_config_path(root)

def save_config(root: str | Path, cfg: SkillConfig, path: str | Path | None = None) -> Path:
    path = Path(path) if path else config_path(root)
    if path.suffix.lower() == '.json':
        path.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        path.write_text(dump_yaml_text(cfg.to_dict()), encoding='utf-8')
    return path

def _from_dict(doc: dict[str, Any]) -> SkillConfig:
    def _worker(raw: Any) -> WorkerConfig:
        if isinstance(raw, WorkerConfig):
            return raw
        if isinstance(raw, str):
            # Backward compatibility: older configs used plain strings like "local".
            # The runtime is now always model-backed via OpenClaw workers.
            return WorkerConfig()
        if isinstance(raw, dict):
            return WorkerConfig(**raw)
        return WorkerConfig()

    subagents_raw = doc.get('subagents') or {}
    return SkillConfig(
        agent_workspaces=AgentWorkspaceConfig(**(doc.get('agent_workspaces') or {})),
        subagents=SubagentsConfig(
            dialog_parser=_worker(subagents_raw.get('dialog_parser')),
            domain_builder=_worker(subagents_raw.get('domain_builder')),
            resume_parser=_worker(subagents_raw.get('resume_parser')),
            question_generator=_worker(subagents_raw.get('question_generator')),
            evaluator=_worker(subagents_raw.get('evaluator')),
            case_builder=_worker(subagents_raw.get('case_builder')),
        ),
        paths=PathsConfig(**(doc.get('paths') or {})),
        defaults=DefaultsConfig(**(doc.get('defaults') or {})),
    )

def load_config(root: str | Path) -> SkillConfig:
    path = config_path(root)
    if not path.exists():
        cfg = _default_config()
        save_config(root, cfg, path=path)
        return cfg
    text = path.read_text(encoding='utf-8')
    raw = json.loads(text or '{}') if path.suffix.lower() == '.json' else (load_yaml_text(text) or {})
    cfg = _from_dict(raw if isinstance(raw, dict) else {})
    save_config(root, cfg, path=path)
    return cfg

def initialize_default_config(root: str | Path) -> dict[str, Any]:
    path = config_path(root)
    cfg = load_config(root) if path.exists() else _default_config()
    save_config(root, cfg, path=path)
    return {'config_file': str(path), 'created': True}
