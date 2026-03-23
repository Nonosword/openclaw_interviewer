from __future__ import annotations

from pathlib import Path
from typing import Any

from interviewer.storage.store import Storage


class LocalRetrieval:
    def __init__(self, root: str | Path):
        self.storage = Storage(root)

    def load_domain_questions(self, *, jd_id: str | None = None, knowledge_id: str | None = None) -> list[dict[str, Any]]:
        domain_id = jd_id or knowledge_id
        if not domain_id:
            raise ValueError('missing_jd_id')
        return self.storage.read_jsonl(self.storage.domain_q_dir / f'{domain_id}.questions.jsonl')

    def load_resume_questions(self, resume_profile_file: str) -> list[dict[str, Any]]:
        profile = self.load_resume_profile(resume_profile_file)
        bank_ref = str(profile.get('resume_question_bank_ref') or '')
        if not bank_ref:
            raise ValueError('resume_question_bank_missing')
        return self.storage.read_jsonl(self._resume_artifact_path(bank_ref))

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
        payload = self.storage.load_json(self._resume_artifact_path(resume_profile_file)) or {}
        if not payload:
            raise ValueError('resume_profile_missing')
        return payload

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
