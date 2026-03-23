from __future__ import annotations

from pathlib import Path
from typing import Any

from interviewer.storage.store import Storage


class LocalRetrieval:
    def __init__(self, root: str | Path):
        self.storage = Storage(root)

    def select_initial_questions(self, *, jd_id: str | None = None, knowledge_id: str | None = None, resume_file: str, question_distribution: dict[str, int], resume_count: int) -> list[dict[str, Any]]:
        domain_id = jd_id or knowledge_id
        if not domain_id:
            raise ValueError("missing_jd_id")
        domain_rows = self.storage.read_jsonl(self.storage.domain_q_dir / f"{domain_id}.questions.jsonl")
        resume_rows = self.storage.read_jsonl(self._resume_artifact_path(f"data/{self._resume_artifact_key(resume_file)}.questions.jsonl"))
        selected: list[dict[str, Any]] = []
        for difficulty, count in question_distribution.items():
            bucket = [row for row in domain_rows if row.get("difficulty") == difficulty][:count]
            selected.extend(bucket)
        selected.extend(resume_rows[:resume_count])
        return selected

    def retrieve_domain_evidence(self, jd_id: str | None = None, query: str = "", knowledge_id: str | None = None) -> list[dict[str, Any]]:
        domain_id = jd_id or knowledge_id
        if not domain_id:
            raise ValueError("missing_jd_id")
        rows = self.storage.read_jsonl(self.storage.domain_dir / f"{domain_id}.jsonl")
        return self._score_rows(rows, query, text_key="evidence")[:4]

    def retrieve_resume_evidence(self, resume_profile_file: str, query: str) -> list[dict[str, Any]]:
        doc = self.storage.load_json(self._resume_artifact_path(resume_profile_file)) or {}
        rows = (doc.get("evidence_chunks") or [])
        return self._score_rows(rows, query, text_key="text")[:4]

    def load_resume_profile(self, resume_profile_file: str) -> dict[str, Any]:
        return self.storage.load_json(self._resume_artifact_path(resume_profile_file)) or {}

    def summarize_weak_topics(self, history: list[dict[str, Any]]) -> list[str]:
        weak = []
        for row in history:
            if float(((row.get("score") or {}).get("overall") or 0)) < 6.5:
                weak.append(str(row.get("topic") or row.get("question_text") or ""))
        return list(dict.fromkeys([x for x in weak if x]))[:5]

    def _score_rows(self, rows: list[dict[str, Any]], query: str, text_key: str) -> list[dict[str, Any]]:
        q = set(query.lower().split())
        scored = []
        for row in rows:
            text = str(row.get(text_key) or row)
            tokens = set(text.lower().split())
            score = len(q & tokens)
            if score or not q:
                scored.append({**row, "_score": score})
        return sorted(scored, key=lambda x: x.get("_score", 0), reverse=True)

    def _resume_artifact_path(self, relative_name: str) -> Path:
        candidate = self.storage.resume_dir / relative_name
        if candidate.exists():
            return candidate
        return self.storage.resume_data_dir / Path(relative_name).name

    def _resume_artifact_key(self, resume_file: str) -> str:
        return str(resume_file).replace("\\", "/").replace("/", "__").replace(":", "_")
