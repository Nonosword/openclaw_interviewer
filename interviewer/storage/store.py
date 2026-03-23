from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, root: str | Path, rag_root: str = ".rag", workspace_root: str = ".workspace"):
        self.root = Path(root)
        self.rag_dir = self.root / rag_root
        self.domain_dir = self.rag_dir / "domain"
        self.domain_q_dir = self.rag_dir / "domain_question_bank"
        self.jd_dir = self.rag_dir / "jd"
        self.resume_dir = self.rag_dir / "resume"
        self.resume_data_dir = self.resume_dir / "data"
        self.candidate_dir = self.rag_dir / "candidates"
        self.retrieval_dir = self.rag_dir / "retrieval"
        self.workspace = self.root / workspace_root
        self.runtime_dir = self.workspace / "runtime"
        self.interviews_dir = self.workspace / "interviews"
        self.scores_dir = self.workspace / "scores"
        self.timers_dir = self.workspace / "timers"
        self.logs_dir = self.workspace / "logs"
        self.candidates_path = self.candidate_dir / "candidate.jsonl"
        self.jd_path = self.jd_dir / "jd.jsonl"
        self.interview_records_path = self.interviews_dir / "interview_records.jsonl"
        self.score_records_path = self.scores_dir / "score_records.jsonl"
        self.timers_path = self.timers_dir / "timers.jsonl"
        self.events_path = self.logs_dir / "events.jsonl"
        self.audit_path = self.logs_dir / "audit.jsonl"
        self.retrieval_manifest_path = self.retrieval_dir / "manifest.json"
        self._ensure()

    def _ensure(self) -> None:
        for p in [
            self.rag_dir, self.domain_dir, self.domain_q_dir, self.jd_dir, self.resume_dir, self.resume_data_dir, self.candidate_dir,
            self.retrieval_dir, self.workspace, self.runtime_dir, self.interviews_dir,
            self.scores_dir, self.timers_dir, self.logs_dir,
        ]:
            p.mkdir(parents=True, exist_ok=True)
        for f in [self.candidates_path, self.jd_path, self.interview_records_path, self.score_records_path, self.timers_path, self.events_path, self.audit_path]:
            if not f.exists():
                f.write_text("", encoding="utf-8")
        if not self.retrieval_manifest_path.exists():
            self.save_json(self.retrieval_manifest_path, {"version": 4, "indexes": {}})

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def rewrite_jsonl_by_key(self, path: Path, key: str, value: str, payload: dict[str, Any]) -> None:
        rows = self.read_jsonl(path)
        found = False
        new_rows = []
        for row in rows:
            if row.get(key) == value:
                new_rows.append(payload)
                found = True
            else:
                new_rows.append(row)
        if not found:
            new_rows.append(payload)
        self.write_jsonl(path, new_rows)

    def save_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def load_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def save_runtime(self, session_id: str, payload: dict[str, Any]) -> None:
        self.save_json(self.runtime_dir / f"interview_{session_id}.json", payload)

    def load_runtime(self, session_id: str) -> dict[str, Any] | None:
        return self.load_json(self.runtime_dir / f"interview_{session_id}.json")

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.append_jsonl(self.events_path, {"type": event_type, "payload": payload})

    def audit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.append_jsonl(self.audit_path, {"type": event_type, "payload": payload})

    def update_manifest(self, key: str, value: Any) -> None:
        manifest = self.load_json(self.retrieval_manifest_path) or {"version": 4, "indexes": {}}
        manifest.setdefault("indexes", {})[key] = value
        self.save_json(self.retrieval_manifest_path, manifest)
