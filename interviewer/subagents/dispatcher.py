from __future__ import annotations

import json
import re
import subprocess
import uuid
from json import JSONDecoder
from pathlib import Path
from typing import Any

from interviewer.config.schema import SubagentsConfig, WorkerConfig
from interviewer.subagents import schemas


class LocalSubagentDispatcher:
    def __init__(self, root: str | Path | None = None, subagents: SubagentsConfig | None = None):
        self.root = Path(root) if root is not None else None
        self.subagents = subagents or SubagentsConfig()

    def slugify_knowledge(self, role_name: str) -> str:
        return 'knowledge_' + ''.join(ch if ch.isalnum() else '_' for ch in role_name.lower()).strip('_')

    def parse_candidate_dialog(self, dialog_text: str, resume_file: str | None = None) -> dict[str, Any]:
        payload = {
            'dialog_text': str(dialog_text or ''),
            'resume_file': resume_file,
        }
        response = self._invoke_json_worker(
            worker_name='dialog_parser',
            task_name='parse_candidate_dialog',
            payload=payload,
            instructions=(
                '从管理员提供的自然语言文本中提取候选人信息。'
                '只依据输入文本，不要补造缺失信息。'
                '输出一个 JSON object，字段必须包括 candidate_name、scheduled_at、interview_role、jd_text、resume_file。'
                '如果输入里没有 resume_file，就使用 payload.resume_file；如果两者都没有，也必须返回空字符串而不是虚构路径。'
                'scheduled_at 保持原文 ISO8601 风格；jd_text 保留管理员表达的岗位描述正文。'
            ),
        )
        return schemas.validate_dialog_candidate(response)

    def build_domain_items(self, jd_role: str, jd_text: str, jd_id: str) -> list[dict[str, Any]]:
        payload = {
            'jd_id': jd_id,
            'jd_role': jd_role,
            'jd_text': jd_text,
        }
        response = self._invoke_json_worker(
            worker_name='domain_builder',
            task_name='build_domain_items',
            payload=payload,
            instructions=(
                '基于岗位名称和 JD 正文，生成一组适合技术面试知识库入库的 domain items。'
                '输出一个 JSON array，每个元素必须包含 jd_id、jd_role、topic、subtopic、difficulty、keywords、ideal_points、anti_patterns、evidence。'
                'difficulty 只能是 easy、medium、hard。'
                'topic 和 subtopic 必须具体、可区分，避免重复；keywords 至少 4 个；ideal_points 和 anti_patterns 分别给 3-5 条；evidence 要引用 JD 中的真实能力要求。'
                '整体覆盖基础能力、核心工程能力、稳定性/安全/架构等层次，不要使用模板化空话。'
            ),
        )
        return schemas.validate_domain_items(response)

    def build_domain_questions(self, role_name: str, jd_text: str, knowledge_id: str, domain_items: list[dict[str, Any]], per_topic: int = 4) -> list[dict[str, Any]]:
        payload = {
            'knowledge_id': knowledge_id,
            'jd_role': role_name,
            'jd_text': jd_text,
            'per_topic': per_topic,
            'domain_items': domain_items,
        }
        expected_count = max(len(domain_items), 1) * max(int(per_topic or 0), 1)
        instructions = (
            '基于输入的 domain_items 生成岗位题库。'
            '输出一个 JSON array。每个 domain item 必须生成恰好 per_topic 道题。'
            '每道题必须包含 question_id、knowledge_id、source、difficulty、topic、question、ideal_answer_points、scoring_focus、followup_hints、evidence_refs。'
            'source 固定为 domain；knowledge_id 使用输入值；difficulty 必须与对应 domain item 一致；topic 使用对应 subtopic。'
            '题目必须彼此明显不同，同一 topic 下不能重复，只能依据给定 JD 与 domain_items 推导。'
            'ideal_answer_points 给 3-5 条，scoring_focus 给 3-5 个维度，followup_hints 给 2-4 条。'
        )
        questions = self._generate_unique_question_bank(
            worker_name='question_generator',
            task_name='build_domain_questions',
            payload=payload,
            instructions=instructions,
            expected_count=expected_count,
        )
        return schemas.validate_question_bank(questions)

    def parse_resume_text(self, resume_text: str, candidate_name: str | None, role_name: str, jd_text: str, resume_file: str) -> dict[str, Any]:
        payload = {
            'candidate_name': candidate_name,
            'role_name': role_name,
            'jd_text': jd_text,
            'resume_file': resume_file,
            'resume_text': resume_text,
        }
        response = self._invoke_json_worker(
            worker_name='resume_parser',
            task_name='parse_resume_text',
            payload=payload,
            instructions=(
                '基于简历文本和目标岗位，提取结构化简历画像。'
                '输出一个 JSON object，字段必须包括 resume_id、resume_file、candidate_name、parsed、job_fit、resume_question_bank_ref、evidence_chunks。'
                'parsed 必须包含 skills、projects、experience_years、raw_excerpt；projects 每项至少包含 name、summary、keywords。'
                'job_fit 必须包含 job_role、fit_score、fit_reason、matched_keywords、gaps；fit_score 取 0-100。'
                'evidence_chunks 必须是可追溯的简历证据切片，每项包含 chunk_id、text、keywords。'
                '不要用关键词硬匹配式思路敷衍，要根据简历上下文做真实归纳。'
            ),
        )
        return schemas.validate_resume_profile(response)

    def build_resume_questions(self, resume_profile: dict[str, Any], role_name: str, jd_text: str) -> list[dict[str, Any]]:
        payload = {
            'resume_profile': resume_profile,
            'role_name': role_name,
            'jd_text': jd_text,
            'question_count': 6,
        }
        instructions = (
            '基于简历画像和目标岗位，生成 6 道与候选人经历强相关的面试题。'
            '输出一个 JSON array，每项必须包含 question_id、knowledge_id、source、difficulty、topic、question、ideal_answer_points、scoring_focus、followup_hints、evidence_refs。'
            'source 固定为 resume；knowledge_id 设为 null。'
            '题目要覆盖项目真实性、职责边界、技术取舍、结果指标、岗位匹配风险等方面，不能只是改写同一句话。'
            '整体至少覆盖 medium 和 hard 两种难度。'
        )
        questions = self._generate_unique_question_bank(
            worker_name='question_generator',
            task_name='build_resume_questions',
            payload=payload,
            instructions=instructions,
            expected_count=6,
        )
        return schemas.validate_question_bank(questions)

    def build_case_question(self, role_name: str, jd_text: str, resume_profile: dict[str, Any], history: list[dict[str, Any]], knowledge_id: str | None, weak_topics: list[str] | None = None) -> dict[str, Any]:
        payload = {
            'role_name': role_name,
            'jd_text': jd_text,
            'resume_profile': resume_profile,
            'history': history,
            'knowledge_id': knowledge_id,
            'weak_topics': weak_topics or [],
        }
        response = self._invoke_json_worker(
            worker_name='case_builder',
            task_name='build_case_question',
            payload=payload,
            instructions=(
                '基于岗位 JD、候选人简历画像和前面作答历史，生成 1 道综合 case 题。'
                '输出一个 JSON object，字段必须包括 question_id、knowledge_id、source、difficulty、topic、question、ideal_answer_points、scoring_focus、followup_hints、evidence_refs。'
                'source 固定为 case；difficulty 固定为 hard；topic 用“综合案例”或更具体但同义的主题。'
                '题目必须综合候选人背景与岗位要求，并优先针对 weak_topics 暴露出的薄弱点设计。'
            ),
        )
        return schemas.validate_case_question(response)

    def _generate_unique_question_bank(
        self,
        *,
        worker_name: str,
        task_name: str,
        payload: dict[str, Any],
        instructions: str,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        retry_note = ''
        last_error: ValueError | None = None
        for _ in range(2):
            response = self._invoke_json_worker(
                worker_name=worker_name,
                task_name=task_name,
                payload=payload,
                instructions=instructions + retry_note,
            )
            try:
                questions = schemas.validate_question_bank(response)
                self._validate_question_bank_constraints(questions, expected_count=expected_count)
                return questions
            except ValueError as exc:
                last_error = exc
                retry_note = (
                    '\nAdditional correction rule: the previous output violated question-bank constraints. '
                    'Regenerate the full set with exact count and no duplicated question texts.'
                )
        raise last_error or ValueError('question_bank_generation_failed')

    def _validate_question_bank_constraints(self, questions: list[dict[str, Any]], *, expected_count: int) -> None:
        if len(questions) != expected_count:
            raise ValueError('question_bank_count_invalid')
        seen: set[str] = set()
        for row in questions:
            key = self._normalize_question_text(str(row.get('question') or ''))
            if not key or key in seen:
                raise ValueError('question_bank_has_duplicates')
            seen.add(key)

    def _invoke_json_worker(
        self,
        *,
        worker_name: str,
        task_name: str,
        payload: dict[str, Any],
        instructions: str,
    ) -> Any:
        worker = getattr(self.subagents, worker_name)
        prompt = self._build_prompt(task_name=task_name, instructions=instructions, payload=payload)
        envelope = self._run_openclaw_agent(worker=worker, prompt=prompt, task_name=task_name)
        text = self._extract_payload_text(envelope)
        try:
            return self._parse_json_text(text)
        except Exception as exc:
            raise ValueError(
                'subagent_invalid_json_response',
                {
                    'task_name': task_name,
                    'worker_name': worker_name,
                    'raw_text': text[:4000],
                    'error_detail': f'{exc.__class__.__name__}: {exc}',
                },
            ) from exc

    def _build_prompt(self, *, task_name: str, instructions: str, payload: dict[str, Any]) -> str:
        return (
            'You are an OpenClaw subagent worker for the openclaw_interviewer skill.\n'
            'Return JSON only. Do not use markdown fences. Do not explain your reasoning.\n'
            'Only analyze the provided payload. Do not fabricate files, IDs, times, or experience.\n'
            'If something is missing, leave it empty/null instead of inventing.\n'
            f'Task: {task_name}\n'
            f'Instructions: {instructions}\n'
            'Payload JSON:\n'
            f'{json.dumps(payload, ensure_ascii=False, indent=2)}\n'
        )

    def _run_openclaw_agent(self, *, worker: WorkerConfig, prompt: str, task_name: str) -> dict[str, Any]:
        command = [
            'openclaw',
            'agent',
            '--agent',
            worker.agent_id,
            '--json',
            '--thinking',
            worker.thinking,
            '--timeout',
            str(worker.timeout_seconds),
            '--session-id',
            f'interviewer-{task_name}-{uuid.uuid4().hex[:10]}',
            '--message',
            prompt,
        ]
        try:
            proc = subprocess.run(
                command,
                cwd=str(self.root) if self.root is not None else None,
                capture_output=True,
                text=True,
                timeout=max(int(worker.timeout_seconds or 0), 1) + 30,
                check=False,
            )
        except Exception as exc:
            raise ValueError(
                'subagent_exec_failed',
                {
                    'task_name': task_name,
                    'agent_id': worker.agent_id,
                    'error_detail': f'{exc.__class__.__name__}: {exc}',
                },
            ) from exc
        if proc.returncode != 0:
            raise ValueError(
                'subagent_exec_failed',
                {
                    'task_name': task_name,
                    'agent_id': worker.agent_id,
                    'stdout': proc.stdout[-4000:],
                    'stderr': proc.stderr[-4000:],
                },
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                'subagent_response_not_json',
                {
                    'task_name': task_name,
                    'agent_id': worker.agent_id,
                    'stdout': proc.stdout[-4000:],
                    'stderr': proc.stderr[-4000:],
                },
            ) from exc

    def _extract_payload_text(self, envelope: dict[str, Any]) -> str:
        payloads = (((envelope or {}).get('result') or {}).get('payloads') or [])
        texts = [str(item.get('text') or '') for item in payloads if str(item.get('text') or '').strip()]
        if not texts:
            raise ValueError(
                'subagent_empty_payload',
                {
                    'envelope_status': envelope.get('status'),
                    'summary': envelope.get('summary'),
                },
            )
        return '\n'.join(texts).strip()

    def _parse_json_text(self, text: str) -> Any:
        stripped = str(text or '').strip()
        candidates = [stripped]
        if stripped.startswith('```'):
            fenced = re.sub(r'^```[a-zA-Z0-9_]*\n?', '', stripped)
            fenced = re.sub(r'\n?```$', '', fenced)
            candidates.append(fenced.strip())
        decoder = JSONDecoder()
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            for idx, ch in enumerate(candidate):
                if ch not in '[{':
                    continue
                try:
                    obj, end = decoder.raw_decode(candidate[idx:])
                except json.JSONDecodeError:
                    continue
                if candidate[idx + end:].strip():
                    continue
                return obj
        raise ValueError('json_payload_not_found')

    def _normalize_question_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', str(text or '').strip().lower())
