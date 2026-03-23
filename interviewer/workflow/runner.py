from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from interviewer.capabilities.local import LocalCapabilities
from interviewer.capabilities.registry import CapabilityRegistry
from interviewer.capabilities.retrieval import LocalRetrieval
from interviewer.config.loader import load_config
from interviewer.core.communication import Communicator
from interviewer.core.models import InterviewRuntime, new_id
from interviewer.core.security import SecurityPolicy
from interviewer.simple_yaml import load_yaml_text
from interviewer.workflow.steps import InterviewStepHandlers, WorkflowStepRecorder


class WorkflowRunner:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.config = load_config(self.root)
        self.defaults = self.config.defaults.to_dict()
        self.cap = LocalCapabilities(self.root, self.config)
        self.retrieval = LocalRetrieval(self.root)
        self.comm = Communicator()
        self.security = SecurityPolicy()
        self.registry = CapabilityRegistry()
        self._register()
        self.workflow_specs = self._load_workflow_specs()
        self.step_recorder = WorkflowStepRecorder()
        self.steps = InterviewStepHandlers(self)

    def _register(self) -> None:
        self.registry.register('jd.list', self.cap.jd_list)
        self.registry.register('jd.upsert', self.cap.jd_upsert, side_effect=True)
        self.registry.register('candidate.lookup', self.cap.candidate_lookup)
        self.registry.register('candidate.upsert', self.cap.candidate_upsert, side_effect=True)
        self.registry.register('candidate.remove', self.cap.candidate_remove, side_effect=True)
        self.registry.register('candidate.initialize', self.cap.candidate_initialize, side_effect=True)
        self.registry.register('candidate.bulk_update', self.cap.candidate_bulk_update, side_effect=True)
        self.registry.register('candidate.bulk_remove', self.cap.candidate_bulk_remove, side_effect=True)
        self.registry.register('candidate.add_from_dialog', self.cap.candidate_add_from_dialog, side_effect=True)
        self.registry.register('domain.ensure', self.cap.domain_ensure, side_effect=True)
        self.registry.register('domain.generate_knowledge', self.cap.domain_generate_knowledge, side_effect=True)
        self.registry.register('question_bank.generate', self.cap.question_bank_generate, side_effect=True)
        self.registry.register('resume.parse_pdf', self.cap.resume_parse_pdf)
        self.registry.register('resume.build_profile', self.cap.resume_build_profile, side_effect=True)
        self.registry.register('resume.generate_questions', self.cap.resume_generate_questions, side_effect=True)
        self.registry.register('timer.ensure', self.cap.timer_ensure, side_effect=True)
        self.registry.register('retrieval.inspect', self.cap.retrieval_inspect)
        self.registry.register('runtime.load', self.cap.runtime_load)
        self.registry.register('runtime.save', self.cap.runtime_save, side_effect=True)
        self.registry.register('evaluation.score_answer', self.cap.evaluation_score_answer)
        self.registry.register('case.generate', self.cap.case_generate)
        self.registry.register('interview.record_write', self.cap.interview_record_write, side_effect=True)
        self.registry.register('event.write', self.cap.event_write, side_effect=True)
        self.registry.register('audit.write', self.cap.audit_write, side_effect=True)

    def _load_workflow_specs(self) -> dict[str, Any]:
        specs = {}
        wf_dir = self.root / 'workflows'
        if wf_dir.exists():
            for path in wf_dir.glob('*.yaml'):
                if path.name.startswith('._'):
                    continue
                specs[path.stem] = load_yaml_text(path.read_text(encoding='utf-8')) or {}
        return specs

    def consume_step_traces(self) -> list[dict[str, Any]]:
        return self.step_recorder.consume()

    def admin_config_show(self) -> dict[str, Any]:
        return self.config.to_dict()

    def admin_capabilities(self) -> dict[str, Any]:
        items = self.registry.list()
        return {'items': items, 'count': len(items)}

    def admin_jd_list(self) -> dict[str, Any]:
        return self.registry.execute('jd.list')

    def admin_jd_upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.registry.execute('jd.upsert', payload=payload)
        self.registry.execute('event.write', event_type='jd_upserted', payload={'jd_id': result['jd_id']})
        self.step_recorder.record('admin_ops', 'jd_upsert', state_before=None, state_after='updated', jd_id=result['jd_id'])
        return {'item': result}

    def admin_candidate_list(self) -> dict[str, Any]:
        rows = self.cap.load_candidates()
        items = []
        for idx, row in enumerate(rows, start=1):
            item = dict(row)
            item['index'] = idx
            items.append(item)
        return {'items': items, 'count': len(items)}

    def admin_candidate_upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.registry.execute('candidate.upsert', payload=payload)
        initialization = None
        initialization_error = None
        if item.get('enabled', True):
            try:
                initialization = self.registry.execute('candidate.initialize', candidate_id=item['candidate_id'])
                item = self._load_candidate(item['candidate_id'])
            except ValueError as exc:
                initialization_error = self._value_error_payload(exc)
                item = self._mark_candidate_initialization_failed(item['candidate_id'], initialization_error['error_code'])
                self.registry.execute('event.write', event_type='candidate_initialization_failed', payload={'candidate_id': item['candidate_id'], 'error_code': initialization_error['error_code']})
        self.registry.execute('event.write', event_type='candidate_upserted', payload={'candidate_id': item['candidate_id']})
        self.step_recorder.record('admin_ops', 'candidate_upsert', state_before=None, state_after=item.get('status', 'updated'), candidate_id=item['candidate_id'], auto_initialized=bool(initialization), initialization_error=(initialization_error or {}).get('error_code'))
        return {'item': item, 'initialized': bool(initialization), 'initialization': initialization, 'initialization_error': initialization_error, 'ok': initialization_error is None}

    def admin_candidate_add_from_dialog(self, dialog_text: str, resume_file: str | None = None, candidate_id: str | None = None) -> dict[str, Any]:
        item = self.registry.execute('candidate.add_from_dialog', dialog_text=dialog_text, resume_file=resume_file, candidate_id=candidate_id)
        initialization = None
        initialization_error = None
        if item.get('enabled', True):
            try:
                initialization = self.registry.execute('candidate.initialize', candidate_id=item['candidate_id'])
                item = self._load_candidate(item['candidate_id'])
            except ValueError as exc:
                initialization_error = self._value_error_payload(exc)
                item = self._mark_candidate_initialization_failed(item['candidate_id'], initialization_error['error_code'])
                self.registry.execute('event.write', event_type='candidate_initialization_failed', payload={'candidate_id': item['candidate_id'], 'error_code': initialization_error['error_code']})
        self.registry.execute('event.write', event_type='candidate_added_from_dialog', payload={'candidate_id': item['candidate_id']})
        self.step_recorder.record('admin_ops', 'candidate_add_from_dialog', state_before=None, state_after=item.get('status', 'created'), candidate_id=item['candidate_id'], auto_initialized=bool(initialization), initialization_error=(initialization_error or {}).get('error_code'))
        return {'item': item, 'initialized': bool(initialization), 'initialization': initialization, 'initialization_error': initialization_error, 'ok': initialization_error is None}

    def admin_candidate_bulk_update(self, candidate_ids: list[str] | None = None, indices: list[int] | None = None, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.registry.execute('candidate.bulk_update', candidate_ids=candidate_ids, indices=indices, updates=updates)
        self.registry.execute('event.write', event_type='candidate_bulk_updated', payload=result)
        self.step_recorder.record('admin_ops', 'candidate_bulk_update', state_before=None, state_after='updated', count=result.get('count', 0))
        return result

    def admin_candidate_bulk_remove(self, candidate_ids: list[str] | None = None, indices: list[int] | None = None) -> dict[str, Any]:
        result = self.registry.execute('candidate.bulk_remove', candidate_ids=candidate_ids, indices=indices)
        self.registry.execute('event.write', event_type='candidate_bulk_removed', payload=result)
        self.step_recorder.record('admin_ops', 'candidate_bulk_remove', state_before=None, state_after='removed', count=result.get('count', 0))
        return result

    def admin_candidate_remove(self, candidate_id: str) -> dict[str, Any]:
        result = self.registry.execute('candidate.remove', candidate_id=candidate_id)
        if result.get('removed'):
            self.registry.execute('event.write', event_type='candidate_removed', payload={'candidate_id': candidate_id})
            self.step_recorder.record('admin_ops', 'candidate_remove', state_before=None, state_after='removed', candidate_id=candidate_id)
        return result

    def admin_candidate_initialize(self) -> dict[str, Any]:
        rows = self.cap.storage.read_jsonl(self.cap.storage.candidates_path)
        items = []
        errors = []
        for row in rows:
            if row.get('enabled', True) is False:
                continue
            try:
                items.append(self.registry.execute('candidate.initialize', candidate_id=row['candidate_id']))
            except ValueError as exc:
                error = self._value_error_payload(exc)
                error['candidate_id'] = row['candidate_id']
                self._mark_candidate_initialization_failed(row['candidate_id'], error['error_code'])
                errors.append(error)
        self.registry.execute('event.write', event_type='candidate_init_completed', payload={'count': len(items), 'error_count': len(errors)})
        self.step_recorder.record('candidate_init', 'initialize_candidates', state_before=None, state_after='ready' if not errors else 'partial_failure', count=len(items), error_count=len(errors))
        return {'count': len(items), 'items': items, 'errors': errors, 'ok': not errors, 'workflow': self.workflow_specs.get('candidate_init.lobster') or self.workflow_specs.get('candidate_init')}

    def admin_candidate_refresh(self, candidate_id: str) -> dict[str, Any]:
        try:
            item = self.registry.execute('candidate.initialize', candidate_id=candidate_id)
        except ValueError as exc:
            error = self._value_error_payload(exc)
            item = self._mark_candidate_initialization_failed(candidate_id, error['error_code'])
            self.registry.execute('event.write', event_type='candidate_refresh_failed', payload={'candidate_id': candidate_id, 'error_code': error['error_code']})
            self.step_recorder.record('admin_ops', 'candidate_refresh', state_before=None, state_after=item.get('status', 'failed'), candidate_id=candidate_id, initialization_error=error['error_code'])
            return {'item': item, 'initialization_error': error, 'ok': False}
        self.registry.execute('event.write', event_type='candidate_refreshed', payload={'candidate_id': candidate_id})
        self.step_recorder.record('admin_ops', 'candidate_refresh', state_before=None, state_after='ready', candidate_id=candidate_id)
        return {'item': item, 'ok': True}

    def admin_domain_ensure(self, jd_id: str, jd_role: str | None = None, jd_text: str | None = None) -> dict[str, Any]:
        return self.registry.execute('domain.ensure', jd_id=jd_id, jd_role=jd_role, jd_text=jd_text)

    def admin_domain_generate(self, jd_id: str, jd_role: str | None = None, jd_text: str | None = None) -> dict[str, Any]:
        return self.registry.execute('domain.generate_knowledge', jd_id=jd_id, jd_role=jd_role, jd_text=jd_text)

    def admin_resume_parse(self, resume_file: str, role_name: str, jd_text: str, candidate_name: str | None = None) -> dict[str, Any]:
        return self.registry.execute('resume.build_profile', resume_file=resume_file, role_name=role_name, jd_text=jd_text, candidate_name=candidate_name)

    def admin_timer_ensure(self, candidate_id: str, scheduled_at: str) -> dict[str, Any]:
        return self.registry.execute('timer.ensure', candidate_id=candidate_id, scheduled_at=scheduled_at)

    def admin_retrieval_inspect(self) -> dict[str, Any]:
        result = self.registry.execute('retrieval.inspect')
        self.step_recorder.record('admin_ops', 'retrieval_inspect', state_before=None, state_after='inspected', candidate_count=result.get('candidate_count', 0))
        return result

    def interview_identify(self, candidate_name: str | None = None, candidate_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        session_id = session_id or new_id('sess')
        if not candidate_name or not candidate_id:
            runtime = InterviewRuntime(session_id=session_id, state='WAITING_FOR_IDENTITY')
            self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
            self.step_recorder.record('interview_start', 'request_identity', state_before=None, state_after=runtime.state, session_id=session_id)
            return {'session_id': session_id, 'state': runtime.state, 'visible_message': self.comm.ask_identity()}
        candidate = self.registry.execute('candidate.lookup', candidate_name=candidate_name, candidate_id=candidate_id)
        if not candidate:
            self.registry.execute('audit.write', event_type='candidate_not_found', payload={'session_id': session_id, 'candidate_name': candidate_name, 'candidate_id': candidate_id})
            return {'session_id': session_id, 'matched': False, 'error_code': 'candidate_not_found', 'visible_message': self.comm.identify_fail()}
        runtime = InterviewRuntime(session_id=session_id, state='CANDIDATE_IDENTIFIED', candidate_id=candidate['candidate_id'], candidate_name=candidate['candidate_name'], knowledge_id=candidate.get('jd_id'), resume_profile_file=candidate.get('resume_profile_file'), scheduled_at=candidate.get('scheduled_at'), is_late=self._is_late(candidate.get('scheduled_at')), max_interview_seconds=self.defaults['max_interview_seconds'], max_question_seconds=self.defaults['max_question_seconds'])
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.step_recorder.record('interview_start', 'identify_candidate', state_before='WAITING_FOR_IDENTITY', state_after=runtime.state, session_id=session_id, candidate_id=candidate['candidate_id'])
        self.registry.execute('event.write', event_type='candidate_identified', payload={'session_id': session_id, 'candidate_id': candidate['candidate_id']})
        return {'session_id': session_id, 'matched': True, 'state': runtime.state, 'candidate': {'candidate_name': candidate['candidate_name'], 'candidate_id': candidate['candidate_id'], 'interview_role': candidate['interview_role'], 'scheduled_at': candidate['scheduled_at'], 'jd_id': candidate.get('jd_id')}, 'visible_message': self.comm.identify_success(candidate['candidate_name'], candidate['candidate_id'], candidate['interview_role'], candidate['scheduled_at'])}

    def interview_begin(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        candidate = self._load_candidate(runtime.candidate_id)
        runtime.queue = self.steps.build_initial_queue(runtime, candidate)
        runtime.state = 'INTERVIEW_STARTED'
        runtime.interview_started_at = datetime.now().astimezone().isoformat()
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.step_recorder.record('interview_start', 'start_interview', state_before='CANDIDATE_IDENTIFIED', state_after=runtime.state, session_id=session_id, queue_size=len(runtime.queue))
        self.registry.execute('event.write', event_type='interview_started', payload={'session_id': session_id, 'candidate_id': runtime.candidate_id})
        return {'state': runtime.state, 'queue_size': len(runtime.queue), 'visible_message': self.comm.begin(runtime.is_late), 'workflow': self.workflow_specs.get('interview_start.lobster') or self.workflow_specs.get('interview_start')}

    def interview_status(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        pending = [q for q in runtime.queue if not q.get('asked')]
        return {'session_id': session_id, 'state': runtime.state, 'candidate_id': runtime.candidate_id, 'current_question_id': runtime.current_question_id, 'pending_count': len(pending), 'followup_total_count': runtime.followup_total_count, 'followup_chain_count': runtime.followup_chain_count, 'completed_case': runtime.completed_case}

    def interview_next(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        if runtime.current_question_id and runtime.state == 'WAITING_FOR_REPLY':
            current = self._find_question(runtime, runtime.current_question_id)
            if current.get('asked') and current.get('answer_count', 0) == 0:
                return {'question_id': current['question_id'], 'visible_message': self.comm.ask_question(current['question']), 'state': runtime.state, 'repeated': True}
        pending_selected = self.steps.select_next_question(runtime)
        if not pending_selected:
            if not runtime.completed_case:
                return self.interview_case_generate(session_id)
            return self.interview_finish(session_id)
        q = pending_selected
        q['asked'] = True
        runtime.current_question_id = q['question_id']
        runtime.question_started_at = datetime.now().astimezone().isoformat()
        runtime.asked_question_ids.append(q['question_id'])
        runtime.state = 'WAITING_FOR_REPLY'
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.registry.execute('event.write', event_type='question_asked', payload={'session_id': session_id, 'question_id': q['question_id']})
        return {'question_id': q['question_id'], 'visible_message': self.comm.ask_question(q['question']), 'state': runtime.state}

    def interview_reply(self, session_id: str, candidate_message: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        if self.security.is_internal_probe(candidate_message):
            self.registry.execute('audit.write', event_type='blocked_candidate_probe', payload={'session_id': session_id, 'candidate_id': runtime.candidate_id, 'message': candidate_message[:300]})
            self.step_recorder.record('interview_round', 'deny_probe', state_before=runtime.state, state_after=runtime.state, session_id=session_id, candidate_id=runtime.candidate_id)
            return {'action': 'deny', 'visible_message': self.comm.denied(), 'state': runtime.state}
        question = self._find_question(runtime, runtime.current_question_id)
        question['answer_count'] = int(question.get('answer_count', 0)) + 1
        score = self.steps.score_answer(runtime, question, candidate_message)
        self.cap.storage.append_jsonl(self.cap.storage.score_records_path, score)
        question['_latest_missing_points'] = score['coverage']['missing_points']
        self._replace_question(runtime, question)
        self.registry.execute('event.write', event_type='reply_scored', payload={'session_id': session_id, 'question_id': question['question_id'], 'overall': score['score']['overall']})
        followup = self.steps.maybe_followup(question, candidate_message, runtime, score.get('score', {}).get('overall', 0))
        if followup and question['source'] not in {'case', 'followup'}:
            runtime.followup_total_count += 1
            runtime.followup_chain_count += 1
            followup['asked'] = True
            runtime.current_question_id = followup['question_id']
            runtime.question_started_at = datetime.now().astimezone().isoformat()
            runtime.asked_question_ids.append(followup['question_id'])
            runtime.queue = self._insert_after_current(runtime.queue, question['question_id'], followup)
            runtime.state = 'WAITING_FOR_REPLY'
            self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
            self.step_recorder.record('interview_round', 'insert_followup', state_before='EVALUATING_REPLY', state_after=runtime.state, session_id=session_id, source_question_id=question['question_id'], followup_question_id=followup['question_id'])
            self.registry.execute('event.write', event_type='followup_inserted', payload={'session_id': session_id, 'question_id': followup['question_id'], 'source_question_id': question['question_id']})
            return {'action': 'followup', 'question_id': followup['question_id'], 'visible_message': self.comm.followup(followup['question']), 'state': runtime.state, 'awaiting_reply': True}
        runtime.followup_chain_count = 0
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        next_result = self.interview_next(session_id)
        if next_result.get('final'):
            return {'action': 'finish', **next_result}
        return {'action': 'next', **next_result}

    def interview_case_generate(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        candidate = self._load_candidate(runtime.candidate_id)
        case_q = self.steps.generate_case(runtime, candidate)
        case_q.setdefault('source', 'case')
        case_q.setdefault('difficulty', 'hard')
        case_q.setdefault('topic', 'case_final')
        case_q.setdefault('question_id', new_id('case'))
        case_q.setdefault('order', max([q['order'] for q in runtime.queue], default=0) + 1)
        case_q['asked'] = True
        runtime.queue.append(case_q)
        runtime.current_question_id = case_q['question_id']
        runtime.completed_case = True
        runtime.question_started_at = datetime.now().astimezone().isoformat()
        runtime.state = 'WAITING_FOR_REPLY'
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.registry.execute('event.write', event_type='case_generated', payload={'session_id': session_id, 'question_id': case_q['question_id']})
        return {'question_id': case_q['question_id'], 'visible_message': self.comm.ask_question(case_q['question']), 'state': runtime.state, 'workflow': self.workflow_specs.get('interview_case.lobster') or self.workflow_specs.get('interview_case')}

    def interview_finish(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        history = [row for row in self.cap.storage.read_jsonl(self.cap.storage.score_records_path) if row['candidate_id'] == runtime.candidate_id]
        final_meta = self.steps.finalize(runtime, history)
        final_score = final_meta['final_score']
        transcript = []
        for q in sorted(runtime.queue, key=lambda x: x['order']):
            score_row = next((row for row in history if row['question_id'] == q['question_id']), None)
            transcript.append({'question_id': q['question_id'], 'question': q.get('question'), 'source': q.get('source'), 'difficulty': q.get('difficulty'), 'score': (score_row or {}).get('score'), 'reply_text': (score_row or {}).get('reply_text')})
        record = {'session_id': session_id, 'candidate_id': runtime.candidate_id, 'candidate_name': runtime.candidate_name, 'jd_id': runtime.knowledge_id, 'resume_profile_file': runtime.resume_profile_file, 'final_score': final_score, 'subscores': final_meta['subscores'], 'transcript': transcript, 'question_count': len(history), 'finished_at': datetime.now().astimezone().isoformat()}
        self.registry.execute('interview.record_write', payload=record)
        runtime.state = 'COMPLETED'
        self.step_recorder.record('interview_finalize', 'persist_record', state_before='FINAL_EVALUATING', state_after=runtime.state, session_id=session_id, question_count=len(history), final_score=final_score)
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.registry.execute('event.write', event_type='interview_completed', payload={'session_id': session_id, 'candidate_id': runtime.candidate_id, 'final_score': final_score})
        return {'final': True, 'state': runtime.state, 'final_score': final_score, 'visible_message': self.comm.finish(), 'workflow': self.workflow_specs.get('interview_finalize.lobster') or self.workflow_specs.get('interview_finalize')}

    def _load_runtime(self, session_id: str) -> InterviewRuntime:
        payload = self.registry.execute('runtime.load', session_id=session_id)
        if not payload:
            raise ValueError('runtime_not_found')
        return InterviewRuntime(**payload)

    def _load_candidate(self, candidate_id: str | None) -> dict[str, Any]:
        rows = self.cap.load_candidates()
        for row in rows:
            if row.get('candidate_id') == candidate_id:
                return row
        raise ValueError('candidate_not_found')

    def _build_initial_queue(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        queue = []
        for idx, row in enumerate(rows, start=1):
            item = dict(row)
            item.setdefault('question_id', new_id('q'))
            item['order'] = idx
            item['asked'] = False
            item.setdefault('answer_count', 0)
            queue.append(item)
        return queue

    def _find_question(self, runtime: InterviewRuntime, question_id: str | None) -> dict[str, Any]:
        for q in runtime.queue:
            if q.get('question_id') == question_id:
                return q
        raise ValueError('question_not_found')

    def _replace_question(self, runtime: InterviewRuntime, question: dict[str, Any]) -> None:
        for idx, item in enumerate(runtime.queue):
            if item.get('question_id') == question.get('question_id'):
                runtime.queue[idx] = question
                return

    def _insert_after_current(self, queue: list[dict[str, Any]], current_qid: str, followup: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        inserted = False
        for item in queue:
            out.append(item)
            if item.get('question_id') == current_qid and not inserted:
                followup['order'] = item['order'] + 0.1
                out.append(followup)
                inserted = True
        return sorted(out, key=lambda x: x['order'])

    def _maybe_build_followup(self, question: dict[str, Any], reply_text: str, total_count: int, chain_count: int, latest_overall: float, answer_count: int) -> dict[str, Any] | None:
        if total_count >= self.defaults['max_followups_total'] or chain_count >= self.defaults['max_followups_chain']:
            return None
        if answer_count > 1:
            return None
        if question.get('source') in {'followup', 'case'}:
            return None
        missing = list(question.get('_latest_missing_points') or [])
        if missing and float(latest_overall or 0) < 7.6:
            prompt = missing[0]
            return {'question_id': new_id('fq'), 'source': 'followup', 'source_question_id': question['question_id'], 'difficulty': question.get('difficulty', 'medium'), 'topic': question.get('topic', 'followup'), 'question': f'你刚才提到的内容还不够完整。请继续补充：{prompt}', 'ideal_answer_points': [prompt], 'evidence_refs': question.get('evidence_refs', []), 'answer_count': 0}
        text = str(reply_text or '')
        has_case_signal = any(token in text for token in ['项目', '线上', '日志', '监控', '优化'])
        if has_case_signal and len(text) < 80 and float(latest_overall or 0) < 7.2:
            return {'question_id': new_id('fq'), 'source': 'followup', 'source_question_id': question['question_id'], 'difficulty': question.get('difficulty', 'medium'), 'topic': question.get('topic', 'followup'), 'question': '请结合一个真实案例，把你的判断过程、验证方式和结果说得更具体一些。', 'ideal_answer_points': ['背景', '动作', '验证', '结果'], 'evidence_refs': question.get('evidence_refs', []), 'answer_count': 0}
        return None

    def _subscores(self, history: list[dict[str, Any]]) -> dict[str, float]:
        def avg(rows):
            return round(sum(float((r.get('score') or {}).get('overall') or 0) for r in rows) / max(len(rows), 1), 2)
        return {
            'domain': avg([r for r in history if r.get('source') == 'domain']),
            'resume': avg([r for r in history if r.get('source') == 'resume']),
            'followup': avg([r for r in history if r.get('source') == 'followup']),
            'case': avg([r for r in history if r.get('source') == 'case']),
        }

    def _is_late(self, scheduled_at: str | None) -> bool:
        if not scheduled_at:
            return False
        try:
            return datetime.now().astimezone() > datetime.fromisoformat(scheduled_at)
        except Exception:
            return False

    def _value_error_payload(self, exc: ValueError) -> dict[str, Any]:
        payload: dict[str, Any] = {'ok': False, 'error_code': str(exc.args[0] if exc.args else exc)}
        if len(exc.args) > 1 and isinstance(exc.args[1], dict):
            payload.update(exc.args[1])
        return payload

    def _mark_candidate_initialization_failed(self, candidate_id: str, error_code: str) -> dict[str, Any]:
        row = dict(self._load_candidate(candidate_id))
        row['status'] = 'resume_parse_failed' if str(error_code).startswith('resume_') else 'init_failed'
        self.cap.storage.rewrite_jsonl_by_key(self.cap.storage.candidates_path, 'candidate_id', candidate_id, row)
        return self._load_candidate(candidate_id)
