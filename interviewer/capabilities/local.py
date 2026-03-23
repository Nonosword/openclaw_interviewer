from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from interviewer.config.schema import SkillConfig
from interviewer.core.models import CandidateRecord, DomainKnowledgeItem
from interviewer.subagents.dispatcher import LocalSubagentDispatcher
from interviewer.storage.store import Storage


class LocalCapabilities:
    def __init__(self, root: str | Path, config: SkillConfig):
        self.root = Path(root)
        self.storage = Storage(self.root)
        self.subagents = LocalSubagentDispatcher(self.root, config.subagents)
        self.defaults = config.defaults.to_dict()

    def load_candidates(self) -> list[dict[str, Any]]:
        rows = self.storage.read_jsonl(self.storage.candidates_path)
        normalized_rows: list[dict[str, Any]] = []
        changed = False
        for row in rows:
            normalized = self._normalize_candidate_row(row)
            normalized_rows.append(normalized)
            if normalized != row:
                changed = True
        if changed:
            self.storage.write_jsonl(self.storage.candidates_path, normalized_rows)
            self.storage.update_manifest("candidate_index", {"count": len(normalized_rows)})
        return normalized_rows

    def jd_list(self) -> dict[str, Any]:
        rows = self.storage.read_jsonl(self.storage.jd_path)
        items = sorted(rows, key=lambda row: str(row.get("jd_id") or ""))
        return {"items": items, "count": len(items)}

    def jd_lookup(self, jd_id: str) -> dict[str, Any]:
        return self._get_jd(jd_id)

    def jd_upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._resolve_or_create_jd(
            jd_id=payload.get("jd_id"),
            jd_name=payload.get("jd_name"),
            jd_role=payload.get("jd_role"),
            jd_text=payload.get("jd_text"),
        )

    def candidate_lookup(self, candidate_name: str, candidate_id: str) -> dict[str, Any] | None:
        for row in self.load_candidates():
            if row.get("enabled", True) is False:
                continue
            if row.get("candidate_id", "").strip().lower() == candidate_id.strip().lower() and row.get("candidate_name", "").strip().lower() == candidate_name.strip().lower():
                return row
        return None

    def candidate_upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        interview_role = self._require_nonempty_text("interview_role", payload.get("interview_role"))
        resume_path = self._resolve_resume_path(self._require_nonempty_text("resume_file", payload.get("resume_file")))
        self._validate_resume_source(resume_path)
        jd = self._resolve_or_create_jd(
            jd_id=payload.get("jd_id"),
            jd_name=payload.get("jd_name") or interview_role,
            jd_role=payload.get("jd_role") or interview_role,
            jd_text=payload.get("jd_text"),
        )
        row = CandidateRecord(
            candidate_id=self._require_nonempty_text("candidate_id", payload.get("candidate_id")),
            candidate_name=self._require_nonempty_text("candidate_name", payload.get("candidate_name")),
            interview_role=interview_role,
            jd_id=jd["jd_id"],
            resume_file=str(resume_path),
            scheduled_at=self._require_nonempty_text("scheduled_at", payload.get("scheduled_at")),
            resume_profile_file=payload.get("resume_profile_file"),
            question_bank_id=payload.get("question_bank_id"),
            timer_id=payload.get("timer_id"),
            status=payload.get("status", "new"),
        ).to_dict()
        row["enabled"] = payload.get("enabled", True)
        self.storage.rewrite_jsonl_by_key(self.storage.candidates_path, "candidate_id", row["candidate_id"], row)
        self.storage.update_manifest("candidate_index", {"count": len(self.load_candidates())})
        return row

    def candidate_remove(self, candidate_id: str) -> dict[str, Any]:
        rows = self.load_candidates()
        new_rows = [r for r in rows if r.get("candidate_id") != candidate_id]
        removed = len(new_rows) != len(rows)
        self.storage.write_jsonl(self.storage.candidates_path, new_rows)
        self.storage.update_manifest("candidate_index", {"count": len(new_rows)})
        return {"removed": removed, "candidate_id": candidate_id}

    def candidate_initialize(self, candidate_id: str) -> dict[str, Any]:
        rows = self.load_candidates()
        row = next((r for r in rows if r.get("candidate_id") == candidate_id), None)
        if not row:
            raise ValueError("candidate_not_found")
        jd = self._get_jd(row["jd_id"])
        self.domain_ensure(jd_id=jd["jd_id"], jd_role=jd["jd_role"], jd_text=jd["jd_text"])
        profile = self.resume_build_profile(row["resume_file"], row["interview_role"], jd["jd_text"], row.get("candidate_name"))
        timer = self.timer_ensure(candidate_id=row["candidate_id"], scheduled_at=row["scheduled_at"])
        row["question_bank_id"] = f"{jd['jd_id']}.questions"
        row["resume_profile_file"] = f"data/{self._resume_artifact_key(row['resume_file'])}.profile.json"
        row["timer_id"] = timer["timer_id"]
        row["status"] = "ready"
        self.candidate_upsert(row)
        return {
            "candidate_id": row["candidate_id"],
            "jd_id": jd["jd_id"],
            "resume_profile_file": row["resume_profile_file"],
            "fit_score": profile["fit_score"],
            "timer_id": timer["timer_id"],
        }

    def domain_ensure(self, jd_id: str, jd_role: str | None = None, jd_text: str | None = None) -> dict[str, Any]:
        jd = self._resolve_domain_jd(jd_id, jd_role, jd_text)
        domain_file = self.storage.domain_dir / f"{jd['jd_id']}.jsonl"
        q_file = self.storage.domain_q_dir / f"{jd['jd_id']}.questions.jsonl"
        created = False
        if not domain_file.exists() or not q_file.exists():
            self.domain_generate_knowledge(jd_id=jd["jd_id"], jd_role=jd["jd_role"], jd_text=jd["jd_text"])
            created = True
        return {
            "jd_id": jd["jd_id"],
            "domain_file": str(domain_file.relative_to(self.storage.root)),
            "question_bank_file": str(q_file.relative_to(self.storage.root)),
            "created": created,
        }

    def domain_generate_knowledge(self, jd_id: str, jd_role: str | None = None, jd_text: str | None = None) -> dict[str, Any]:
        jd = self._resolve_domain_jd(jd_id, jd_role, jd_text)
        items = [DomainKnowledgeItem(**item).to_dict() for item in self.subagents.build_domain_items(jd["jd_role"], jd["jd_text"], jd["jd_id"])]
        self.storage.write_jsonl(self.storage.domain_dir / f"{jd['jd_id']}.jsonl", items)
        questions = self.question_bank_generate(jd_id=jd["jd_id"], jd_role=jd["jd_role"], jd_text=jd["jd_text"], domain_items=items)
        self.storage.update_manifest(f"domain:{jd['jd_id']}", {"jd_id": jd["jd_id"], "jd_role": jd["jd_role"], "domain_items": len(items), "questions": len(questions["items"])})
        return {
            "jd_id": jd["jd_id"],
            "domain_items": len(items),
            "questions": len(questions["items"]),
            "domain_file": str((self.storage.domain_dir / f"{jd['jd_id']}.jsonl").relative_to(self.storage.root)),
            "question_bank_file": str((self.storage.domain_q_dir / f"{jd['jd_id']}.questions.jsonl").relative_to(self.storage.root)),
        }

    def question_bank_generate(self, jd_id: str, jd_role: str, jd_text: str, domain_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if domain_items is None:
            domain_items = self.storage.read_jsonl(self.storage.domain_dir / f"{jd_id}.jsonl")
        questions = self.subagents.build_domain_questions(jd_role, jd_text, jd_id, domain_items, per_topic=4)
        self.storage.write_jsonl(self.storage.domain_q_dir / f"{jd_id}.questions.jsonl", questions)
        return {"jd_id": jd_id, "items": questions}

    def resume_parse_pdf(self, resume_file: str) -> dict[str, Any]:
        file_path = self._resolve_resume_path(resume_file)
        artifact_key = self._resume_artifact_key(resume_file)
        txt_sidecar = file_path if file_path.suffix.lower() in {".txt", ".md"} else Path(f"{file_path}.txt")
        extract_sidecar = self.storage.resume_data_dir / f"{artifact_key}.extract.json"
        error_sidecar = self.storage.resume_data_dir / f"{artifact_key}.extract.error.json"
        self._validate_resume_source(file_path)
        if txt_sidecar.exists():
            text = txt_sidecar.read_text(encoding="utf-8")
            normalized = self._normalize_text(text)
            if not normalized:
                raise ValueError("resume_text_empty")
            result = {"resume_file": resume_file, "text": normalized, "engine": "sidecar_txt", "chars": len(normalized)}
            self.storage.save_json(extract_sidecar, result)
            self._clear_sidecar(error_sidecar)
            return result
        if extract_sidecar.exists():
            saved = self.storage.load_json(extract_sidecar) or {}
            text = self._normalize_text(str(saved.get("text") or ""))
            if text:
                return {"resume_file": resume_file, "text": text, "engine": saved.get("engine", "sidecar_extract"), "chars": len(text)}
        attempts: list[dict[str, Any]] = []
        engine = "none"
        text = ""
        for candidate_engine, extractor in [
            ("pdfplumber", self._extract_text_with_pdfplumber),
            ("pypdf", self._extract_text_with_pypdf),
            ("pdfminer_python_fallback", self._extract_text_with_pdfminer),
        ]:
            extracted = self._attempt_resume_extraction(candidate_engine, extractor, file_path, attempts)
            if extracted:
                engine = candidate_engine
                text = extracted
                break
        if not text:
            primary_failure = self._summarize_resume_extract_failure(attempts)
            failure = {
                "resume_file": resume_file,
                "parse_stage": "extract_text",
                "primary_failure_kind": primary_failure.get("failure_kind"),
                "primary_failure_engine": primary_failure.get("engine"),
                "primary_failure_detail": primary_failure.get("detail"),
                "attempted_engines": attempts,
                "admin_message": self._format_resume_extract_admin_message(resume_file, attempts, primary_failure),
                "recommended_actions": [
                    "重新上传简历文件",
                    "执行 openclaw-interviewer admin candidate-refresh --candidate-id <candidate_id>",
                    "或批量执行 openclaw-interviewer admin candidate-initialize",
                ],
            }
            self.storage.save_json(error_sidecar, failure)
            raise ValueError("resume_parse_failed", failure)
        result = {"resume_file": resume_file, "text": text, "engine": engine, "chars": len(text)}
        self.storage.save_json(extract_sidecar, result)
        self._clear_sidecar(error_sidecar)
        if text:
            self.storage.save_text(self.storage.resume_data_dir / f"{artifact_key}.txt", text)
        return result

    def resume_build_profile(self, resume_file: str, role_name: str, jd_text: str, candidate_name: str | None = None) -> dict[str, Any]:
        extracted = self.resume_parse_pdf(resume_file)
        artifact_key = self._resume_artifact_key(resume_file)
        profile_error_sidecar = self.storage.resume_data_dir / f"{artifact_key}.profile.error.json"
        try:
            profile = self.subagents.parse_resume_text(extracted.get("text", ""), candidate_name, role_name, jd_text, resume_file)
        except ValueError as exc:
            failure = {
                "resume_file": resume_file,
                "parse_stage": "build_profile",
                "extract_engine": extracted.get("engine"),
                "error_detail": str(exc.args[0] if exc.args else exc),
                "admin_message": "简历文本已抽取，但结构化解析失败。请检查 PDF 是否可读，必要时重新上传后重新初始化该 candidate。",
            }
            self.storage.save_json(profile_error_sidecar, failure)
            raise ValueError("resume_profile_build_failed", failure) from exc
        self.storage.save_json(self.storage.resume_data_dir / f"{artifact_key}.profile.json", profile)
        self._clear_sidecar(profile_error_sidecar)
        questions = self.resume_generate_questions(profile, role_name, jd_text)
        fit_score = ((profile.get("job_fit") or {}).get("fit_score") or 0)
        return {
            "resume_profile_file": f"data/{artifact_key}.profile.json",
            "resume_question_bank_file": f"data/{artifact_key}.questions.jsonl",
            "fit_score": fit_score,
            "questions": len(questions["items"]),
        }

    def resume_generate_questions(self, resume_profile: dict[str, Any], role_name: str, jd_text: str) -> dict[str, Any]:
        questions = self.subagents.build_resume_questions(resume_profile, role_name, jd_text)
        resume_file = resume_profile["resume_file"]
        artifact_key = self._resume_artifact_key(resume_file)
        self.storage.write_jsonl(self.storage.resume_data_dir / f"{artifact_key}.questions.jsonl", questions)
        return {"resume_file": resume_file, "items": questions}

    def timer_ensure(self, candidate_id: str, scheduled_at: str) -> dict[str, Any]:
        timer_id = f"timer_{candidate_id}"
        row = {
            "timer_id": timer_id,
            "candidate_id": candidate_id,
            "scheduled_at": scheduled_at,
            "late_grace_seconds": self.defaults.get("late_grace_seconds", 0),
            "max_interview_seconds": self.defaults.get("max_interview_seconds", 3600),
            "max_question_seconds": self.defaults.get("max_question_seconds", 300),
            "status": "scheduled",
        }
        self.storage.rewrite_jsonl_by_key(self.storage.timers_path, "timer_id", timer_id, row)
        return row

    def retrieval_inspect(self) -> dict[str, Any]:
        return {
            "manifest": self.storage.load_json(self.storage.retrieval_manifest_path),
            "domain_files": sorted(p.name for p in self.storage.domain_dir.glob("*.jsonl")),
            "resume_profiles": sorted(f"data/{p.name}" for p in self.storage.resume_data_dir.glob("*.profile.json")),
            "candidate_count": len(self.load_candidates()),
            "jd_count": len(self.storage.read_jsonl(self.storage.jd_path)),
        }

    def runtime_load(self, session_id: str) -> dict[str, Any] | None:
        return self.storage.load_runtime(session_id)

    def runtime_save(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.storage.save_runtime(session_id, payload)
        return {"session_id": session_id, "saved": True}

    def evaluation_score_answer(self, question: dict[str, Any], reply_text: str, candidate_id: str, started_at: str | None, max_question_seconds: int, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        from interviewer.capabilities.scoring import score_answer
        return score_answer(question, reply_text, candidate_id, started_at, max_question_seconds, evidence or [])

    def case_generate(self, role_name: str, jd_text: str, resume_profile: dict[str, Any], history: list[dict[str, Any]], knowledge_id: str | None, weak_topics: list[str] | None = None) -> dict[str, Any]:
        return self.subagents.build_case_question(role_name, jd_text, resume_profile, history, knowledge_id, weak_topics or [])

    def interview_record_write(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.storage.append_jsonl(self.storage.interview_records_path, payload)
        return {"written": True, "candidate_id": payload.get("candidate_id")}

    def event_write(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.storage.log_event(event_type, payload)
        return {"written": True, "event_type": event_type}

    def audit_write(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.storage.audit(event_type, payload)
        return {"written": True, "event_type": event_type}

    def candidate_bulk_update(self, candidate_ids: list[str] | None = None, indices: list[int] | None = None, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = self.load_candidates()
        target_ids = set(candidate_ids or [])
        if indices:
            for idx in indices:
                if 1 <= int(idx) <= len(rows):
                    target_ids.add(rows[int(idx) - 1].get("candidate_id"))
        updates = dict(updates or {})
        changed = []
        new_rows = []
        for row in rows:
            if row.get("candidate_id") in target_ids:
                row = dict(row)
                row.update(updates)
                changed.append(row.get("candidate_id"))
            new_rows.append(row)
        self.storage.write_jsonl(self.storage.candidates_path, new_rows)
        return {"updated_ids": changed, "count": len(changed)}

    def candidate_bulk_remove(self, candidate_ids: list[str] | None = None, indices: list[int] | None = None) -> dict[str, Any]:
        rows = self.load_candidates()
        target_ids = set(candidate_ids or [])
        if indices:
            for idx in indices:
                if 1 <= int(idx) <= len(rows):
                    target_ids.add(rows[int(idx) - 1].get("candidate_id"))
        new_rows = [r for r in rows if r.get("candidate_id") not in target_ids]
        self.storage.write_jsonl(self.storage.candidates_path, new_rows)
        self.storage.update_manifest("candidate_index", {"count": len(new_rows)})
        return {"removed_ids": sorted(target_ids), "count": len(target_ids)}

    def candidate_add_from_dialog(self, dialog_text: str, resume_file: str | None = None, candidate_id: str | None = None) -> dict[str, Any]:
        if not resume_file:
            raise ValueError("missing_resume_file")
        parsed = self.subagents.parse_candidate_dialog(dialog_text, resume_file=resume_file)
        row = {
            "candidate_id": candidate_id or f"C{len(self.load_candidates()) + 1:07d}",
            "candidate_name": parsed["candidate_name"],
            "interview_role": parsed["interview_role"],
            "jd_name": parsed.get("jd_name") or parsed["interview_role"],
            "jd_role": parsed.get("jd_role") or parsed["interview_role"],
            "jd_text": parsed["jd_text"],
            "resume_file": parsed["resume_file"],
            "scheduled_at": parsed["scheduled_at"],
            "status": "new",
            "enabled": True,
        }
        return self.candidate_upsert(row)

    def _normalize_text(self, text: str) -> str:
        lines = [" ".join(line.split()) for line in (text or "").splitlines()]
        return "\n".join([ln for ln in lines if ln]).strip()

    def _normalize_candidate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        normalized.pop("knowledge_id", None)
        legacy_jd_text = normalized.pop("jd_text", None)
        if not normalized.get("jd_id"):
            preferred_id = row.get("knowledge_id") if str(row.get("knowledge_id") or "").strip() else None
            jd = self._resolve_or_create_jd(
                jd_id=row.get("jd_id"),
                jd_name=normalized.get("interview_role"),
                jd_role=normalized.get("interview_role"),
                jd_text=legacy_jd_text,
                preferred_id=preferred_id,
            )
            normalized["jd_id"] = jd["jd_id"]
        normalized.setdefault("question_bank_id", f"{normalized['jd_id']}.questions")
        normalized.setdefault("enabled", True)
        resume_profile_file = str(normalized.get("resume_profile_file") or "").strip()
        if resume_profile_file and not resume_profile_file.startswith("data/"):
            normalized["resume_profile_file"] = f"data/{self._resume_artifact_key(normalized['resume_file'])}.profile.json"
        return normalized

    def _resolve_domain_jd(self, jd_id: str, jd_role: str | None, jd_text: str | None) -> dict[str, Any]:
        if jd_role and jd_text:
            return self._resolve_or_create_jd(jd_id=jd_id, jd_name=jd_role, jd_role=jd_role, jd_text=jd_text)
        return self._get_jd(jd_id)

    def _resolve_or_create_jd(
        self,
        jd_id: str | None = None,
        jd_name: str | None = None,
        jd_role: str | None = None,
        jd_text: str | None = None,
        preferred_id: str | None = None,
    ) -> dict[str, Any]:
        rows = self.storage.read_jsonl(self.storage.jd_path)
        requested_id = str(jd_id or "").strip()
        if requested_id:
            existing = next((row for row in rows if row.get("jd_id") == requested_id), None)
            if not existing:
                if jd_text is None:
                    raise ValueError("jd_not_found")
                jd_role_text = self._require_nonempty_text("jd_role", jd_role)
                jd_text_value = self._require_nonempty_text("jd_text", jd_text)
                self._validate_material_text("jd_text", jd_text_value)
                row = {
                    "jd_id": requested_id,
                    "jd_name": self._require_nonempty_text("jd_name", jd_name or jd_role_text),
                    "jd_role": jd_role_text,
                    "jd_text": jd_text_value,
                }
                self.storage.rewrite_jsonl_by_key(self.storage.jd_path, "jd_id", requested_id, row)
                return row
            if jd_name or jd_role or jd_text:
                updated = dict(existing)
                updated["jd_name"] = self._require_nonempty_text("jd_name", jd_name or existing.get("jd_name") or existing.get("jd_role"))
                updated["jd_role"] = self._require_nonempty_text("jd_role", jd_role or existing.get("jd_role"))
                updated["jd_text"] = self._require_nonempty_text("jd_text", jd_text or existing.get("jd_text"))
                self._validate_material_text("jd_text", updated["jd_text"])
                self.storage.rewrite_jsonl_by_key(self.storage.jd_path, "jd_id", requested_id, updated)
                return updated
            return existing
        if jd_text is None:
            raise ValueError("missing_jd_id_or_jd_text")
        jd_role_text = self._require_nonempty_text("jd_role", jd_role)
        jd_text_value = self._require_nonempty_text("jd_text", jd_text)
        self._validate_material_text("jd_text", jd_text_value)
        jd_name_value = self._require_nonempty_text("jd_name", jd_name or jd_role_text)
        for row in rows:
            if row.get("jd_role") == jd_role_text and row.get("jd_text") == jd_text_value:
                if row.get("jd_name") != jd_name_value:
                    updated = dict(row)
                    updated["jd_name"] = jd_name_value
                    self.storage.rewrite_jsonl_by_key(self.storage.jd_path, "jd_id", updated["jd_id"], updated)
                    return updated
                return row
        base_id = str(preferred_id or "").strip() or self._jd_id_base(jd_name_value, jd_role_text)
        jd_id_value = self._next_jd_id(base_id, rows)
        row = {
            "jd_id": jd_id_value,
            "jd_name": jd_name_value,
            "jd_role": jd_role_text,
            "jd_text": jd_text_value,
        }
        self.storage.rewrite_jsonl_by_key(self.storage.jd_path, "jd_id", jd_id_value, row)
        return row

    def _get_jd(self, jd_id: str) -> dict[str, Any]:
        target = self._require_nonempty_text("jd_id", jd_id)
        for row in self.storage.read_jsonl(self.storage.jd_path):
            if row.get("jd_id") == target:
                return row
        raise ValueError("jd_not_found")

    def _jd_id_base(self, jd_name: str, jd_role: str) -> str:
        seed = str(jd_name or jd_role or "jd").strip().lower()
        slug = "".join(ch if ch.isalnum() else "_" for ch in seed).strip("_")
        return f"jd_{slug or 'default'}"

    def _next_jd_id(self, base_id: str, rows: list[dict[str, Any]]) -> str:
        existing_ids = {str(row.get("jd_id") or "") for row in rows}
        if base_id not in existing_ids:
            return base_id
        idx = 2
        while f"{base_id}_{idx}" in existing_ids:
            idx += 1
        return f"{base_id}_{idx}"

    def _resume_artifact_key(self, resume_file: str) -> str:
        return str(resume_file).replace("\\", "/").replace("/", "__").replace(":", "_")

    def _resolve_resume_path(self, resume_file: str) -> Path:
        raw = Path(resume_file).expanduser()
        candidates = []
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.append(raw)
            candidates.append(self.root / raw)
            candidates.append(self.storage.resume_dir / raw.name)
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        raise ValueError("resume_file_not_found")

    def _validate_resume_source(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise ValueError("resume_file_not_found")
        if path.stat().st_size == 0:
            raise ValueError("resume_file_empty")
        if path.suffix.lower() in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                raise ValueError("resume_text_empty")
            self._validate_material_text("resume_file", text)

    def _validate_material_text(self, field: str, text: str) -> None:
        normalized = text.strip()
        if len(normalized) < 8:
            raise ValueError(f"{field}_too_short")
        lower = normalized.lower()
        if any(marker in lower for marker in ["placeholder", "占位", "todo", "tbd", "简历内容（占位）", "简历内容(占位)"]):
            raise ValueError(f"{field}_placeholder_detected")

    def _require_nonempty_text(self, field: str, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"missing_{field}")
        return text

    def _attempt_resume_extraction(self, engine: str, extractor: Any, file_path: Path, attempts: list[dict[str, Any]]) -> str:
        try:
            text = self._normalize_text(str(extractor(file_path) or ""))
        except Exception as exc:
            failure_kind = "missing_dependency" if isinstance(exc, (ImportError, ModuleNotFoundError)) else "parser_error"
            attempts.append({
                "engine": engine,
                "ok": False,
                "failure_kind": failure_kind,
                "error": f"{exc.__class__.__name__}: {exc}"[:240],
            })
            return ""
        attempts.append({
            "engine": engine,
            "ok": bool(text),
            "failure_kind": "empty_text" if not text else None,
            "chars": len(text),
        })
        return text

    def _extract_text_with_pdfplumber(self, file_path: Path) -> str:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    def _extract_text_with_pypdf(self, file_path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    def _extract_text_with_pdfminer(self, file_path: Path) -> str:
        from pdfminer.high_level import extract_text

        return extract_text(str(file_path))

    def _clear_sidecar(self, path: Path) -> None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()

    def _summarize_resume_extract_failure(self, attempts: list[dict[str, Any]]) -> dict[str, Any]:
        for kind in ["missing_dependency", "parser_error", "empty_text"]:
            for attempt in attempts:
                if attempt.get("failure_kind") == kind:
                    return {
                        "engine": attempt.get("engine"),
                        "failure_kind": kind,
                        "detail": attempt.get("error") or f"{attempt.get('engine')} returned no text",
                    }
        return {"engine": None, "failure_kind": "unknown", "detail": "no_extractors_succeeded"}

    def _format_resume_extract_admin_message(self, resume_file: str, attempts: list[dict[str, Any]], primary_failure: dict[str, Any]) -> str:
        stage = f"简历解析失败：在 extract_text 阶段读取 {resume_file} 时出错。"
        summary = f"首要失败点为 {primary_failure.get('engine') or 'unknown'}，原因：{primary_failure.get('failure_kind') or 'unknown'}"
        if primary_failure.get("detail"):
            summary += f"（{primary_failure['detail']}）"
        details = []
        for attempt in attempts:
            if attempt.get("ok"):
                details.append(f"{attempt['engine']}: ok(chars={attempt.get('chars', 0)})")
            elif attempt.get("failure_kind") == "empty_text":
                details.append(f"{attempt['engine']}: empty_text")
            else:
                details.append(f"{attempt['engine']}: {attempt.get('failure_kind', 'failed')} [{attempt.get('error', 'no_detail')}]")
        return f"{stage} {summary}。尝试结果：{'；'.join(details)}。请提供可读的 PDF/TXT 简历文件或重新上传后再执行。"
