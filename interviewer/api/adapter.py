from __future__ import annotations

from pathlib import Path
from typing import Any

from interviewer.workflow.runner import WorkflowRunner


class OpenClawAdapter:
    def __init__(self, root: str | Path):
        self.runner = WorkflowRunner(root)

    def dispatch(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if endpoint == 'openclaw.admin.config.show':
                result = self.runner.admin_config_show()
            elif endpoint == 'openclaw.admin.capabilities.list':
                result = self.runner.admin_capabilities()
            elif endpoint == 'openclaw.admin.jd.list':
                result = self.runner.admin_jd_list()
            elif endpoint == 'openclaw.admin.jd.upsert':
                result = self.runner.admin_jd_upsert(payload)
            elif endpoint == 'openclaw.admin.domain.ensure':
                result = self.runner.admin_domain_ensure(payload['jd_id'], payload.get('jd_role'), payload.get('jd_text'))
            elif endpoint == 'openclaw.admin.domain.generate':
                result = self.runner.admin_domain_generate(payload['jd_id'], payload.get('jd_role'), payload.get('jd_text'))
            elif endpoint == 'openclaw.admin.resume.parse':
                result = self.runner.admin_resume_parse(payload['resume_file'], payload['role_name'], payload['jd_text'], payload.get('candidate_name'))
            elif endpoint == 'openclaw.admin.candidate.initialize':
                result = self.runner.admin_candidate_initialize()
            elif endpoint == 'openclaw.admin.timer.ensure':
                result = self.runner.admin_timer_ensure(payload['candidate_id'], payload['scheduled_at'])
            elif endpoint == 'openclaw.admin.candidate.list':
                result = self.runner.admin_candidate_list()
            elif endpoint == 'openclaw.admin.candidate.upsert':
                result = self.runner.admin_candidate_upsert(payload)
            elif endpoint == 'openclaw.admin.candidate.add_from_dialog':
                result = self.runner.admin_candidate_add_from_dialog(payload['dialog_text'], payload.get('resume_file'), payload.get('candidate_id'))
            elif endpoint == 'openclaw.admin.candidate.bulk_update':
                result = self.runner.admin_candidate_bulk_update(payload.get('candidate_ids'), payload.get('indices'), payload.get('updates'))
            elif endpoint == 'openclaw.admin.candidate.bulk_remove':
                result = self.runner.admin_candidate_bulk_remove(payload.get('candidate_ids'), payload.get('indices'))
            elif endpoint == 'openclaw.admin.candidate.remove':
                result = self.runner.admin_candidate_remove(payload['candidate_id'])
            elif endpoint == 'openclaw.admin.candidate.refresh':
                result = self.runner.admin_candidate_refresh(payload['candidate_id'])
            elif endpoint == 'openclaw.admin.retrieval.inspect':
                result = self.runner.admin_retrieval_inspect()
            elif endpoint == 'openclaw.interview.identify':
                result = self.runner.interview_identify(payload.get('candidate_name'), payload.get('candidate_id'), payload.get('session_id'))
            elif endpoint == 'openclaw.interview.begin':
                result = self.runner.interview_begin(payload['session_id'])
            elif endpoint == 'openclaw.interview.status':
                result = self.runner.interview_status(payload['session_id'])
            elif endpoint == 'openclaw.interview.next':
                result = self.runner.interview_next(payload['session_id'])
            elif endpoint == 'openclaw.interview.reply':
                result = self.runner.interview_reply(payload['session_id'], payload.get('candidate_message', ''))
            elif endpoint == 'openclaw.interview.case_generate':
                result = self.runner.interview_case_generate(payload['session_id'])
            elif endpoint == 'openclaw.interview.finish':
                result = self.runner.interview_finish(payload['session_id'])
            else:
                raise ValueError('unsupported_endpoint')
        except ValueError as exc:
            result = self._value_error_payload(exc)
        except KeyError as exc:
            result = {'ok': False, 'error_code': f'missing_field:{exc.args[0]}'}
        traces = self.runner.consume_step_traces()
        if traces:
            result = dict(result)
            result['_step_traces'] = traces
        return result

    def _value_error_payload(self, exc: ValueError) -> dict[str, Any]:
        payload: dict[str, Any] = {'ok': False, 'error_code': str(exc.args[0] if exc.args else exc)}
        if len(exc.args) > 1 and isinstance(exc.args[1], dict):
            payload.update(exc.args[1])
        return payload
