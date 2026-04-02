from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from interviewer.capabilities.local import LocalCapabilities
from interviewer.capabilities.registry import CapabilityRegistry
from interviewer.capabilities.retrieval import LocalRetrieval
from interviewer.config.loader import load_config
from interviewer.core.communication import Communicator
from interviewer.core.models import InterviewRuntime, ensure_question_id, new_id, question_id_prefix
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
        self.registry.register('candidate.initialize', self._candidate_init_workflow, side_effect=True)
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
        self.registry.register('interview.plan', self.cap.interview_build_plan)
        self.registry.register('evaluation.score_answer', self.cap.evaluation_score_answer)
        self.registry.register('followup.generate', self.cap.followup_generate)
        self.registry.register('case.generate', self.cap.case_generate)
        self.registry.register('interview.record_write', self.cap.interview_record_write, side_effect=True)
        self.registry.register('candidate.attach_interview_summary', self.cap.candidate_attach_interview_summary, side_effect=True)
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
        runtime.case_question_count = 0
        runtime.completed_case = False
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.step_recorder.record('interview_start', 'start_interview', state_before='CANDIDATE_IDENTIFIED', state_after=runtime.state, session_id=session_id, queue_size=len(runtime.queue))
        self.registry.execute('event.write', event_type='interview_started', payload={'session_id': session_id, 'candidate_id': runtime.candidate_id})
        return {'state': runtime.state, 'queue_size': len(runtime.queue), 'visible_message': self.comm.begin(runtime.is_late), 'workflow': self.workflow_specs.get('interview_start.lobster') or self.workflow_specs.get('interview_start')}

    def interview_status(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        pending = [q for q in runtime.queue if not q.get('asked')]
        return {'session_id': session_id, 'state': runtime.state, 'candidate_id': runtime.candidate_id, 'current_question_id': runtime.current_question_id, 'pending_count': len(pending), 'followup_total_count': runtime.followup_total_count, 'followup_chain_count': runtime.followup_chain_count, 'completed_case': runtime.completed_case, 'case_question_count': runtime.case_question_count, 'plan_summary': runtime.plan_summary}

    def interview_next(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        if runtime.current_question_id and runtime.state == 'WAITING_FOR_REPLY':
            current = self._find_question(runtime, runtime.current_question_id)
            if current.get('asked') and current.get('answer_count', 0) == 0:
                return {'question_id': current['question_id'], 'visible_message': self.comm.ask_question(current['question']), 'state': runtime.state, 'repeated': True}
        pending_selected = self.steps.select_next_question(runtime)
        if not pending_selected:
            if runtime.case_question_count < int(self.defaults['initial_case_question_count']):
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
        received_at = datetime.now().astimezone().isoformat()
        reply_record = self._build_reply_record(runtime, question, candidate_message, received_at=received_at)
        self.cap.storage.append_jsonl(self.cap.storage.score_records_path, reply_record)
        self.registry.execute('event.write', event_type='reply_received', payload={'session_id': session_id, 'question_id': question['question_id'], 'reply_id': reply_record['reply_id']})
        question['answer_count'] = int(question.get('answer_count', 0)) + 1
        try:
            score = self.steps.score_answer(runtime, question, candidate_message, received_at=received_at)
        except ValueError as exc:
            error_payload = self._value_error_payload(exc)
            failed_record = self._merge_reply_record_error(reply_record, error_payload)
            self.cap.storage.rewrite_jsonl_by_key(self.cap.storage.score_records_path, 'reply_id', reply_record['reply_id'], failed_record)
            self.registry.execute(
                'event.write',
                event_type='reply_score_failed',
                payload={'session_id': session_id, 'question_id': question['question_id'], 'reply_id': reply_record['reply_id'], 'error_code': failed_record['error_code']},
            )
            raise
        score = self._merge_reply_record_success(reply_record, score, session_id=session_id)
        self.cap.storage.rewrite_jsonl_by_key(self.cap.storage.score_records_path, 'reply_id', reply_record['reply_id'], score)
        question['_latest_matched_points'] = score['coverage']['matched_points']
        question['_latest_missing_points'] = score['coverage']['missing_points']
        question['_latest_coverage_ratio'] = score['coverage']['coverage_ratio']
        question['_latest_evidence_ratio'] = score['coverage']['evidence_ratio']
        self._replace_question(runtime, question)
        self.registry.execute('event.write', event_type='reply_scored', payload={'session_id': session_id, 'question_id': question['question_id'], 'overall': score['score']['overall']})
        followup = self.steps.maybe_followup(question, candidate_message, runtime, score.get('score', {}).get('overall', 0))
        if followup and question['source'] not in {'case', 'followup'}:
            runtime.followup_total_count += 1
            runtime.followup_chain_count += 1
            worker_question_id = followup.get('question_id')
            followup['builder_question_id'] = worker_question_id
            followup['source'] = 'followup'
            followup['question_id'] = new_id(question_id_prefix('followup'))
            followup['source_question_id'] = question['question_id']
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
        worker_question_id = case_q.get('question_id')
        case_q.setdefault('source', 'case')
        case_q.setdefault('difficulty', 'hard')
        case_q.setdefault('topic', 'case_final')
        case_q['builder_question_id'] = worker_question_id
        case_q['question_id'] = new_id(question_id_prefix('case'))
        case_q.setdefault('order', max([q['order'] for q in runtime.queue], default=0) + 1)
        case_q['asked'] = True
        runtime.queue.append(case_q)
        runtime.current_question_id = case_q['question_id']
        runtime.case_question_count = int(runtime.case_question_count or 0) + 1
        runtime.completed_case = runtime.case_question_count >= int(self.defaults['initial_case_question_count'])
        runtime.question_started_at = datetime.now().astimezone().isoformat()
        runtime.state = 'WAITING_FOR_REPLY'
        self.registry.execute('runtime.save', session_id=session_id, payload=runtime.to_dict())
        self.registry.execute('event.write', event_type='case_generated', payload={'session_id': session_id, 'question_id': case_q['question_id']})
        return {'question_id': case_q['question_id'], 'visible_message': self.comm.ask_question(case_q['question']), 'state': runtime.state, 'workflow': self.workflow_specs.get('interview_case.lobster') or self.workflow_specs.get('interview_case')}

    def interview_finish(self, session_id: str) -> dict[str, Any]:
        runtime = self._load_runtime(session_id)
        pending_question = self._current_reply_question(runtime)
        if pending_question is not None:
            return {
                'ok': False,
                'error_code': 'reply_pending',
                'question_id': pending_question['question_id'],
                'state': runtime.state,
                'visible_message': self.comm.ask_question(pending_question['question']),
            }
        history = self._session_history(session_id)
        final_meta = self.steps.finalize(runtime, history)
        final_score = final_meta['final_score']
        candidate = self._load_candidate(runtime.candidate_id)
        finished_at = datetime.now().astimezone().isoformat()
        questions = []
        for q in sorted(runtime.queue, key=lambda x: x['order']):
            score_row = next((row for row in history if row['question_id'] == q['question_id']), None)
            questions.append(self._question_summary(q, score_row))
        record = {
            'session_id': session_id,
            'candidate_id': runtime.candidate_id,
            'candidate_name': runtime.candidate_name,
            'interview_role': candidate.get('interview_role'),
            'jd_id': runtime.knowledge_id,
            'resume_profile_file': runtime.resume_profile_file,
            'scheduled_at': runtime.scheduled_at,
            'interview_started_at': runtime.interview_started_at,
            'finished_at': finished_at,
            'status': 'completed',
            'plan_summary': runtime.plan_summary,
            'question_count': len(history),
            'counts_by_type': self._question_type_counts(questions),
            'followup_total_count': runtime.followup_total_count,
            'case_question_count': runtime.case_question_count,
            'final_score': final_score,
            'subscores': final_meta['subscores'],
            'questions': questions,
            'transcript': questions,
        }
        self.registry.execute('interview.record_write', payload=record)
        self.registry.execute('candidate.attach_interview_summary', candidate_id=runtime.candidate_id, interview_summary=record)
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
            item['question_id'] = ensure_question_id(
                item.get('source'),
                item.get('question_id'),
                item.get('knowledge_id'),
                item.get('topic'),
                item.get('difficulty'),
                item.get('question'),
            )
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

    def _record_persistent_step(
        self,
        workflow: str,
        step: str,
        *,
        state_before: str | None,
        state_after: str | None,
        **details: Any,
    ) -> None:
        self.step_recorder.record(workflow, step, state_before=state_before, state_after=state_after, **details)
        self.cap.storage.log_workflow_step(
            {
                'workflow': workflow,
                'step': step,
                'state_before': state_before,
                'state_after': state_after,
                'details': details,
                'timestamp': datetime.now().astimezone().isoformat(),
            }
        )

    def _candidate_init_step_names(self) -> list[str]:
        workflow = self.workflow_specs.get('candidate_init.lobster') or self.workflow_specs.get('candidate_init') or {}
        steps = workflow.get('steps') if isinstance(workflow, dict) else None
        if isinstance(steps, list) and steps:
            return [str(step) for step in steps]
        return [
            'candidate.read_registry',
            'domain.ensure',
            'resume.parse_pdf',
            'resume.build_profile',
            'resume.generate_questions',
            'timer.ensure',
            'candidate.write_registry',
        ]

    def _candidate_init_checkpoint(self, row: dict[str, Any]) -> dict[str, Any]:
        raw = row.get('initialization_checkpoint')
        allowed_steps = set(self._candidate_init_step_names())
        checkpoint = dict(raw) if isinstance(raw, dict) else {}
        completed_steps = [str(step) for step in checkpoint.get('completed_steps', []) if str(step) in allowed_steps]
        checkpoint['workflow'] = 'candidate_init'
        checkpoint['completed_steps'] = completed_steps
        checkpoint['status'] = str(checkpoint.get('status') or 'pending')
        checkpoint['current_step'] = checkpoint.get('current_step')
        checkpoint['last_completed_step'] = checkpoint.get('last_completed_step')
        checkpoint['next_step'] = checkpoint.get('next_step')
        checkpoint['started_at'] = checkpoint.get('started_at')
        checkpoint['updated_at'] = checkpoint.get('updated_at')
        checkpoint['last_error'] = checkpoint.get('last_error') if isinstance(checkpoint.get('last_error'), dict) else None
        return checkpoint

    def _save_candidate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        self.cap.storage.rewrite_jsonl_by_key(self.cap.storage.candidates_path, 'candidate_id', row['candidate_id'], row)
        return self._load_candidate(row['candidate_id'])

    def _candidate_init_error_status(self, error_code: str) -> str:
        return 'resume_parse_failed' if str(error_code).startswith('resume_') else 'init_failed'

    def _candidate_init_registry_ready(self, row: dict[str, Any]) -> bool:
        expected_profile = self.cap._expected_resume_profile_ref(row['resume_file'])
        expected_qbank = f"{row['jd_id']}.questions"
        if str(row.get('resume_profile_file') or '') != expected_profile:
            return False
        if str(row.get('question_bank_id') or '') != expected_qbank:
            return False
        if not self.cap.timer_ready(row['candidate_id'], row['scheduled_at'], row.get('timer_id')):
            return False
        return row.get('status') in {'ready', 'interview_completed'}

    def _candidate_init_step_complete(self, row: dict[str, Any], step: str) -> bool:
        if step == 'candidate.read_registry':
            return True
        if step == 'domain.ensure':
            return self.cap.domain_artifacts_ready(row['jd_id'])
        if step == 'resume.parse_pdf':
            try:
                return self.cap.resume_extract_artifact_ready(row['resume_file'])
            except ValueError:
                return False
        if step == 'resume.build_profile':
            return bool(
                self.cap.storage.load_json(
                    self.cap.storage.resume_data_dir / Path(self.cap._expected_resume_profile_ref(row['resume_file'])).name
                )
            )
        if step == 'resume.generate_questions':
            return self.cap.resume_question_bank_ready(row['resume_file'])
        if step == 'timer.ensure':
            return self.cap.timer_ready(row['candidate_id'], row['scheduled_at'], row.get('timer_id'))
        if step == 'candidate.write_registry':
            return self._candidate_init_registry_ready(row)
        return False

    def _candidate_init_sync_row(self, row: dict[str, Any], step: str) -> dict[str, Any]:
        synced = dict(row)
        if step in {'domain.ensure', 'candidate.write_registry'}:
            synced['question_bank_id'] = f"{synced['jd_id']}.questions"
        if step in {'resume.build_profile', 'resume.generate_questions', 'candidate.write_registry'}:
            synced['resume_profile_file'] = self.cap._expected_resume_profile_ref(synced['resume_file'])
        if step in {'timer.ensure', 'candidate.write_registry'} and self.cap.timer_ready(synced['candidate_id'], synced['scheduled_at'], synced.get('timer_id')):
            synced['timer_id'] = str(synced.get('timer_id') or f"timer_{synced['candidate_id']}")
        if step == 'candidate.write_registry':
            if not synced.get('latest_interview'):
                synced['status'] = 'ready'
            else:
                synced['status'] = 'interview_completed'
        return synced

    def _candidate_init_next_step(self, row: dict[str, Any], steps: list[str]) -> str | None:
        for step in steps:
            if not self._candidate_init_step_complete(row, step):
                return step
        return None

    def _candidate_init_step_summary(self, step: str, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {}
        if step == 'domain.ensure':
            return {'created': bool(result.get('created')), 'jd_id': result.get('jd_id')}
        if step == 'resume.parse_pdf':
            return {'engine': result.get('engine'), 'chars': result.get('chars')}
        if step == 'resume.build_profile':
            return {'resume_profile_file': result.get('resume_profile_file'), 'fit_score': result.get('fit_score')}
        if step == 'resume.generate_questions':
            return {'resume_question_bank_file': result.get('resume_question_bank_file'), 'questions': result.get('questions')}
        if step == 'timer.ensure':
            return {'timer_id': result.get('timer_id')}
        return {}

    def _run_candidate_init_step(self, row: dict[str, Any], step: str) -> tuple[dict[str, Any], dict[str, Any]]:
        working = dict(row)
        jd = self.cap.jd_lookup(working['jd_id'])
        if step == 'candidate.read_registry':
            return working, {'candidate_id': working['candidate_id']}
        if step == 'domain.ensure':
            result = self.cap.domain_ensure(jd_id=jd['jd_id'], jd_role=jd['jd_role'], jd_text=jd['jd_text'])
            working['question_bank_id'] = f"{jd['jd_id']}.questions"
            return working, result
        if step == 'resume.parse_pdf':
            return working, self.cap.resume_parse_pdf(working['resume_file'])
        if step == 'resume.build_profile':
            result = self.cap.resume_profile_generate(working['resume_file'], working['interview_role'], jd['jd_text'], working.get('candidate_name'))
            working['resume_profile_file'] = result['resume_profile_file']
            return working, result
        if step == 'resume.generate_questions':
            result = self.cap.resume_question_bank_generate(working['resume_file'], working['interview_role'], jd['jd_text'])
            working['resume_profile_file'] = self.cap._expected_resume_profile_ref(working['resume_file'])
            return working, result
        if step == 'timer.ensure':
            timer = self.cap.timer_ensure(candidate_id=working['candidate_id'], scheduled_at=working['scheduled_at'])
            working['timer_id'] = timer['timer_id']
            return working, timer
        if step == 'candidate.write_registry':
            working = self._candidate_init_sync_row(working, step)
            return self._save_candidate_row(working), {
                'candidate_id': working['candidate_id'],
                'question_bank_id': working.get('question_bank_id'),
                'resume_profile_file': working.get('resume_profile_file'),
                'timer_id': working.get('timer_id'),
                'status': working.get('status'),
            }
        raise ValueError('candidate_init_step_unsupported')

    def _candidate_init_workflow(self, candidate_id: str) -> dict[str, Any]:
        steps = self._candidate_init_step_names()
        row = dict(self._load_candidate(candidate_id))
        checkpoint = self._candidate_init_checkpoint(row)
        state_before = row.get('status')
        step_outcomes: dict[str, str] = {}
        domain_created = False
        next_step = self._candidate_init_next_step(row, steps)
        if checkpoint.get('started_at') is None:
            checkpoint['started_at'] = datetime.now().astimezone().isoformat()
        checkpoint['status'] = 'completed' if next_step is None else 'in_progress'
        checkpoint['current_step'] = next_step
        checkpoint['next_step'] = next_step
        checkpoint['updated_at'] = datetime.now().astimezone().isoformat()
        checkpoint['last_error'] = None
        row['initialization_checkpoint'] = checkpoint
        if next_step is not None:
            row['status'] = 'initializing'
        row = self._save_candidate_row(row)
        self.registry.execute(
            'event.write',
            event_type='candidate_init_candidate_started',
            payload={'candidate_id': candidate_id, 'resume_from_step': next_step, 'completed_steps': list(checkpoint['completed_steps'])},
        )
        for step in steps:
            row = dict(self._load_candidate(candidate_id))
            checkpoint = self._candidate_init_checkpoint(row)
            if self._candidate_init_step_complete(row, step):
                if step not in checkpoint['completed_steps']:
                    checkpoint['completed_steps'].append(step)
                checkpoint['last_completed_step'] = step
                checkpoint['current_step'] = None
                checkpoint['next_step'] = self._candidate_init_next_step(self._candidate_init_sync_row(row, step), steps)
                checkpoint['updated_at'] = datetime.now().astimezone().isoformat()
                row = self._candidate_init_sync_row(row, step)
                row['initialization_checkpoint'] = checkpoint
                row = self._save_candidate_row(row)
                self.registry.execute(
                    'event.write',
                    event_type='candidate_init_step_skipped',
                    payload={'candidate_id': candidate_id, 'step': step, 'next_step': checkpoint.get('next_step')},
                )
                self._record_persistent_step(
                    'candidate_init',
                    step,
                    state_before=state_before,
                    state_after=row.get('status'),
                    candidate_id=candidate_id,
                    outcome='skipped',
                    next_step=checkpoint.get('next_step'),
                )
                step_outcomes[step] = 'skipped'
                state_before = row.get('status')
                continue
            checkpoint['status'] = 'in_progress'
            checkpoint['current_step'] = step
            checkpoint['next_step'] = step
            checkpoint['updated_at'] = datetime.now().astimezone().isoformat()
            row['initialization_checkpoint'] = checkpoint
            row['status'] = 'initializing'
            row = self._save_candidate_row(row)
            self.registry.execute('event.write', event_type='candidate_init_step_started', payload={'candidate_id': candidate_id, 'step': step})
            try:
                row, result = self._run_candidate_init_step(row, step)
            except ValueError as exc:
                error = self._value_error_payload(exc)
                row = dict(self._load_candidate(candidate_id))
                checkpoint = self._candidate_init_checkpoint(row)
                checkpoint['status'] = 'failed'
                checkpoint['current_step'] = step
                checkpoint['next_step'] = step
                checkpoint['updated_at'] = datetime.now().astimezone().isoformat()
                checkpoint['last_error'] = {'step': step, 'error_code': error['error_code']}
                row['initialization_checkpoint'] = checkpoint
                row['status'] = self._candidate_init_error_status(error['error_code'])
                row = self._save_candidate_row(row)
                self.registry.execute(
                    'event.write',
                    event_type='candidate_init_step_failed',
                    payload={'candidate_id': candidate_id, 'step': step, 'error_code': error['error_code']},
                )
                self.registry.execute(
                    'event.write',
                    event_type='candidate_init_candidate_failed',
                    payload={'candidate_id': candidate_id, 'step': step, 'error_code': error['error_code']},
                )
                self._record_persistent_step(
                    'candidate_init',
                    step,
                    state_before=state_before,
                    state_after=row.get('status'),
                    candidate_id=candidate_id,
                    outcome='failed',
                    error_code=error['error_code'],
                )
                raise
            row = dict(row)
            if step == 'domain.ensure':
                domain_created = bool(result.get('created'))
            checkpoint = self._candidate_init_checkpoint(row)
            if step not in checkpoint['completed_steps']:
                checkpoint['completed_steps'].append(step)
            checkpoint['last_completed_step'] = step
            checkpoint['current_step'] = None
            checkpoint['next_step'] = self._candidate_init_next_step(row, steps)
            checkpoint['updated_at'] = datetime.now().astimezone().isoformat()
            checkpoint['status'] = 'completed' if checkpoint['next_step'] is None else 'in_progress'
            checkpoint['last_error'] = None
            row['initialization_checkpoint'] = checkpoint
            if checkpoint['next_step'] is not None and row.get('status') not in {'ready', 'interview_completed'}:
                row['status'] = 'initializing'
            row = self._save_candidate_row(row)
            summary = self._candidate_init_step_summary(step, result)
            self.registry.execute(
                'event.write',
                event_type='candidate_init_step_completed',
                payload={'candidate_id': candidate_id, 'step': step, **summary, 'next_step': checkpoint.get('next_step')},
            )
            self._record_persistent_step(
                'candidate_init',
                step,
                state_before=state_before,
                state_after=row.get('status'),
                candidate_id=candidate_id,
                outcome='completed',
                next_step=checkpoint.get('next_step'),
                **summary,
            )
            step_outcomes[step] = 'completed'
            state_before = row.get('status')
        row = dict(self._load_candidate(candidate_id))
        checkpoint = self._candidate_init_checkpoint(row)
        checkpoint['status'] = 'completed'
        checkpoint['current_step'] = None
        checkpoint['next_step'] = None
        checkpoint['updated_at'] = datetime.now().astimezone().isoformat()
        checkpoint['last_error'] = None
        row = self._candidate_init_sync_row(row, 'candidate.write_registry')
        row['initialization_checkpoint'] = checkpoint
        row = self._save_candidate_row(row)
        self.registry.execute(
            'event.write',
            event_type='candidate_init_candidate_completed',
            payload={'candidate_id': candidate_id, 'completed_steps': list(checkpoint['completed_steps'])},
        )
        profile_payload = self.cap.storage.load_json(
            self.cap.storage.resume_data_dir / Path(self.cap._expected_resume_profile_ref(row['resume_file'])).name
        ) or {}
        return {
            'candidate_id': row['candidate_id'],
            'jd_id': row['jd_id'],
            'resume_profile_file': row.get('resume_profile_file'),
            'fit_score': ((profile_payload.get('job_fit') or {}).get('fit_score') or 0),
            'timer_id': row.get('timer_id'),
            'domain_created': domain_created,
            'resume_profile_reused': step_outcomes.get('resume.build_profile') == 'skipped',
            'completed_steps': list(checkpoint['completed_steps']),
            'checkpoint_status': checkpoint['status'],
        }

    def _mark_candidate_initialization_failed(self, candidate_id: str, error_code: str) -> dict[str, Any]:
        row = dict(self._load_candidate(candidate_id))
        row['status'] = 'resume_parse_failed' if str(error_code).startswith('resume_') else 'init_failed'
        self.cap.storage.rewrite_jsonl_by_key(self.cap.storage.candidates_path, 'candidate_id', candidate_id, row)
        return self._load_candidate(candidate_id)

    def _session_history(self, session_id: str) -> list[dict[str, Any]]:
        return [
            row for row in self.cap.storage.read_jsonl(self.cap.storage.score_records_path)
            if row.get('session_id') == session_id and self._is_scored_reply_record(row)
        ]

    def _current_reply_question(self, runtime: InterviewRuntime) -> dict[str, Any] | None:
        if runtime.state != 'WAITING_FOR_REPLY' or not runtime.current_question_id:
            return None
        try:
            current = self._find_question(runtime, runtime.current_question_id)
        except ValueError:
            return None
        if current.get('asked') and int(current.get('answer_count') or 0) == 0:
            return current
        return None

    def _build_reply_record(self, runtime: InterviewRuntime, question: dict[str, Any], candidate_message: str, *, received_at: str) -> dict[str, Any]:
        raw_text = '' if candidate_message is None else str(candidate_message)
        return {
            'reply_id': new_id('reply'),
            'reply_status': 'received',
            'session_id': runtime.session_id,
            'candidate_id': runtime.candidate_id,
            'question_id': question.get('question_id'),
            'question_text': question.get('question', ''),
            'source': question.get('source'),
            'difficulty': question.get('difficulty'),
            'topic': question.get('topic'),
            'source_question_id': question.get('source_question_id'),
            'reply_text': raw_text,
            'raw_reply_text': raw_text,
            'normalized_reply_text': raw_text.strip(),
            'timing': {
                'question_started_at': runtime.question_started_at,
                'reply_received_at': received_at,
                'response_seconds': None,
                'max_question_seconds': runtime.max_question_seconds,
            },
            'coverage': None,
            'score': None,
            'reason': None,
            'suggestion': None,
            'evidence_refs': question.get('evidence_refs', []),
            'error_code': None,
            'error_detail': None,
        }

    def _merge_reply_record_success(self, base_record: dict[str, Any], score: dict[str, Any], *, session_id: str) -> dict[str, Any]:
        merged = dict(base_record)
        merged.update(score)
        merged['session_id'] = session_id
        merged['reply_id'] = base_record['reply_id']
        merged['reply_status'] = 'scored'
        merged['raw_reply_text'] = base_record.get('raw_reply_text')
        return merged

    def _merge_reply_record_error(self, base_record: dict[str, Any], error_payload: dict[str, Any]) -> dict[str, Any]:
        failed = dict(base_record)
        failed['reply_status'] = 'error'
        failed['error_code'] = error_payload.get('error_code')
        failed['error_detail'] = error_payload.get('error_detail') or error_payload.get('stderr') or error_payload.get('stdout')
        return failed

    def _is_scored_reply_record(self, row: dict[str, Any]) -> bool:
        status = str(row.get('reply_status') or '')
        if status == 'scored':
            return True
        return row.get('score') is not None and not row.get('error_code')

    def _question_summary(self, question: dict[str, Any], score_row: dict[str, Any] | None) -> dict[str, Any]:
        score_row = score_row or {}
        source = str(question.get('source') or '')
        return {
            'question_id': question.get('question_id'),
            'order': question.get('order'),
            'stage': question.get('stage'),
            'source': source,
            'type': 'knowledge' if source == 'domain' else source,
            'source_question_id': question.get('source_question_id'),
            'topic': question.get('topic'),
            'difficulty': question.get('difficulty'),
            'question': question.get('question'),
            'scoring_focus': question.get('scoring_focus', []),
            'ideal_answer_points': question.get('ideal_answer_points', []),
            'followup_hints': question.get('followup_hints', []),
            'candidate_answer': score_row.get('raw_reply_text') or score_row.get('reply_text'),
            'model_score': score_row.get('score'),
            'overall_score': ((score_row.get('score') or {}).get('overall')),
            'evaluation': {
                'reason': score_row.get('reason'),
                'suggestion': score_row.get('suggestion'),
                'coverage': score_row.get('coverage'),
                'timing': score_row.get('timing'),
            },
            'evidence_refs': question.get('evidence_refs', []),
        }

    def _question_type_counts(self, questions: list[dict[str, Any]]) -> dict[str, int]:
        counts = {'knowledge': 0, 'resume': 0, 'followup': 0, 'case': 0}
        for row in questions:
            qtype = str(row.get('type') or '')
            if qtype in counts:
                counts[qtype] += 1
        return counts
