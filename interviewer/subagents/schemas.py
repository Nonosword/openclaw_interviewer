from __future__ import annotations

from typing import Any

def _expect_type(name: str, value: Any, types: tuple[type, ...]) -> None:
    if not isinstance(value, types):
        raise ValueError(f"{name}_type_invalid")

def _expect_keys(obj: dict[str, Any], keys: list[str]) -> None:
    for key in keys:
        if key not in obj:
            raise ValueError(f"missing_{key}")

def validate_domain_items(payload: Any) -> list[dict[str, Any]]:
    _expect_type('domain_items', payload, (list,))
    if not payload:
        raise ValueError('domain_items_empty')
    for idx, row in enumerate(payload):
        _expect_type(f'domain_item_{idx}', row, (dict,))
        _expect_keys(row, ['jd_id','jd_role','topic','subtopic','difficulty','keywords','ideal_points','anti_patterns','evidence'])
    return payload

def validate_question_bank(payload: Any) -> list[dict[str, Any]]:
    _expect_type('question_bank', payload, (list,))
    if not payload:
        raise ValueError('question_bank_empty')
    for idx, row in enumerate(payload):
        _expect_type(f'question_{idx}', row, (dict,))
        _expect_keys(row, ['question_id','source','difficulty','topic','question','ideal_answer_points','scoring_focus','followup_hints'])
    return payload

def validate_resume_profile(payload: Any) -> dict[str, Any]:
    _expect_type('resume_profile', payload, (dict,))
    _expect_keys(payload, ['resume_id','resume_file','parsed','job_fit','resume_question_bank_ref','evidence_chunks'])
    return payload

def validate_case_question(payload: Any) -> dict[str, Any]:
    _expect_type('case_question', payload, (dict,))
    _expect_keys(payload, ['question_id','source','difficulty','topic','question','ideal_answer_points','scoring_focus','followup_hints'])
    return payload

def validate_dialog_candidate(payload: Any) -> dict[str, Any]:
    _expect_type('dialog_candidate', payload, (dict,))
    _expect_keys(payload, ['candidate_name','scheduled_at','interview_role','jd_text','resume_file'])
    return payload

def validate_interview_plan(payload: Any) -> list[dict[str, Any]]:
    _expect_type('interview_plan', payload, (list,))
    if not payload:
        raise ValueError('interview_plan_empty')
    for idx, row in enumerate(payload):
        _expect_type(f'interview_plan_item_{idx}', row, (dict,))
        _expect_keys(row, ['question_id', 'source', 'order', 'stage'])
    return payload

def validate_score_result(payload: Any) -> dict[str, Any]:
    _expect_type('score_result', payload, (dict,))
    _expect_keys(payload, ['coverage', 'score', 'reason', 'suggestion'])
    _expect_type('score_result_coverage', payload.get('coverage'), (dict,))
    _expect_type('score_result_score', payload.get('score'), (dict,))
    _expect_keys(payload['coverage'], ['matched_points', 'missing_points', 'coverage_ratio', 'evidence_ratio'])
    _expect_keys(payload['score'], ['fluency', 'expression', 'knowledge', 'core_competency', 'case_problem_solving', 'overall'])
    return payload

def validate_followup_question(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if payload is False:
        return None
    if isinstance(payload, dict) and payload.get('followup_needed') is False:
        return None
    _expect_type('followup_question', payload, (dict,))
    _expect_keys(payload, ['question_id','source','difficulty','topic','question','ideal_answer_points','followup_hints'])
    return payload
