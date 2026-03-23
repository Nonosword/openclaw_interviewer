from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from interviewer.config.loader import load_config
from interviewer.storage.store import Storage


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _adapter() -> OpenClawAdapter:
    from interviewer.api.adapter import OpenClawAdapter
    return OpenClawAdapter(_root())


def _storage() -> Storage:
    cfg = load_config(_root())
    return Storage(_root(), rag_root=cfg.paths.rag_root, workspace_root=cfg.paths.workspace_root)


def _dump(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _load_jd(jd_id: str) -> dict[str, Any]:
    for row in _storage().read_jsonl(_storage().jd_path):
        if row.get('jd_id') == jd_id:
            return row
    raise ValueError('jd_not_found')


def _resolve_jd_payload(*, jd_id: str | None, jd_file: str | None, jd_text: str | None, jd_name: str | None, jd_role: str | None) -> dict[str, Any]:
    if jd_id:
        return {'jd_id': jd_id}
    if jd_text:
        return {
            'jd_name': jd_name or jd_role,
            'jd_role': jd_role,
            'jd_text': jd_text,
        }
    if not jd_file:
        raise ValueError('missing_jd_id_or_jd_text')
    return {
        'jd_name': jd_name or jd_role,
        'jd_role': jd_role,
        'jd_text': Path(jd_file).read_text(encoding='utf-8'),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='openclaw-interviewer')
    sub = parser.add_subparsers(dest='lane', required=True)

    sub.add_parser('setup', help='Bootstrap the skill entrypoint and print next steps')

    admin = sub.add_parser('admin', help='Admin lane commands')
    a_sub = admin.add_subparsers(dest='admin_cmd', required=True)
    a_sub.add_parser('config-show')
    a_sub.add_parser('capabilities-list')
    a_sub.add_parser('candidate-list')
    a_sub.add_parser('candidate-initialize')
    a_sub.add_parser('retrieval-inspect')
    a_sub.add_parser('jd-list')
    a_jd = a_sub.add_parser('jd-upsert')
    a_jd.add_argument('--jd-id')
    a_jd.add_argument('--jd-name')
    a_jd.add_argument('--jd-role', required=True)
    a_jd.add_argument('--jd-file')
    a_jd.add_argument('--jd-text')
    a_jd.add_argument('--jd')
    a_domain = a_sub.add_parser('domain-generate')
    a_domain.add_argument('--jd-id')
    a_domain.add_argument('--jd-file')
    a_domain.add_argument('--jd-text')
    a_domain.add_argument('--jd')
    a_domain.add_argument('--jd-name')
    a_domain.add_argument('--jd-role')
    a_parse = a_sub.add_parser('resume-parse')
    a_parse.add_argument('--resume-file', required=True)
    a_parse.add_argument('--role', required=True)
    a_parse.add_argument('--jd-id')
    a_parse.add_argument('--jd-file')
    a_parse.add_argument('--jd-text')
    a_parse.add_argument('--jd')
    a_parse.add_argument('--candidate-name')
    a_upsert = a_sub.add_parser('candidate-upsert')
    a_upsert.add_argument('--candidate-id', required=True)
    a_upsert.add_argument('--name', required=True)
    a_upsert.add_argument('--role', required=True)
    a_upsert.add_argument('--jd-id')
    a_upsert.add_argument('--jd-file')
    a_upsert.add_argument('--jd-text')
    a_upsert.add_argument('--jd')
    a_upsert.add_argument('--jd-name')
    a_upsert.add_argument('--resume-file', required=True)
    a_upsert.add_argument('--scheduled-at', required=True)
    a_upsert.add_argument('--enabled', choices=['true', 'false'], default='true')
    a_add = a_sub.add_parser('candidate-add-from-dialog')
    a_add.add_argument('--dialog-file', required=True)
    a_add.add_argument('--resume-file', required=True)
    a_add.add_argument('--candidate-id')
    a_bulk = a_sub.add_parser('candidate-bulk-update')
    a_bulk.add_argument('--indices', nargs='*', type=int)
    a_bulk.add_argument('--scheduled-at')
    a_bulk.add_argument('--enable', choices=['true', 'false'])
    a_remove = a_sub.add_parser('candidate-bulk-remove')
    a_remove.add_argument('--indices', nargs='*', type=int)
    a_del = a_sub.add_parser('candidate-remove')
    a_del.add_argument('--candidate-id', required=True)
    a_refresh = a_sub.add_parser('candidate-refresh')
    a_refresh.add_argument('--candidate-id', required=True)

    interview = sub.add_parser('interview', help='Candidate lane commands')
    i_sub = interview.add_subparsers(dest='interview_cmd', required=True)
    i_identify = i_sub.add_parser('identify')
    i_identify.add_argument('--candidate-name')
    i_identify.add_argument('--candidate-id')
    i_identify.add_argument('--session-id')
    i_begin = i_sub.add_parser('begin')
    i_begin.add_argument('--session-id', required=True)
    i_status = i_sub.add_parser('status')
    i_status.add_argument('--session-id', required=True)
    i_next = i_sub.add_parser('next')
    i_next.add_argument('--session-id', required=True)
    i_reply = i_sub.add_parser('reply')
    i_reply.add_argument('--session-id', required=True)
    i_reply.add_argument('--candidate-message', required=True)
    i_case = i_sub.add_parser('case-generate')
    i_case.add_argument('--session-id', required=True)
    i_finish = i_sub.add_parser('finish')
    i_finish.add_argument('--session-id', required=True)

    doctor = sub.add_parser('doctor', help='Skill health check')
    doctor.add_argument('--json', action='store_true')

    harness = sub.add_parser('harness', help='Skill harness scenarios')
    harness.add_argument('--scenario', default='full_interview', choices=['identify_only','full_interview','security_probe','transcript_replay','admin_ops'])
    harness.add_argument('--transcript-file')
    harness.add_argument('--output')
    return parser


def run_admin(args: argparse.Namespace) -> int:
    adapter = _adapter()
    if args.admin_cmd == 'config-show':
        _dump(adapter.dispatch('openclaw.admin.config.show', {})); return 0
    if args.admin_cmd == 'capabilities-list':
        _dump(adapter.dispatch('openclaw.admin.capabilities.list', {})); return 0
    if args.admin_cmd == 'candidate-list':
        _dump(adapter.dispatch('openclaw.admin.candidate.list', {})); return 0
    if args.admin_cmd == 'candidate-initialize':
        _dump(adapter.dispatch('openclaw.admin.candidate.initialize', {})); return 0
    if args.admin_cmd == 'retrieval-inspect':
        _dump(adapter.dispatch('openclaw.admin.retrieval.inspect', {})); return 0
    if args.admin_cmd == 'jd-list':
        _dump(adapter.dispatch('openclaw.admin.jd.list', {})); return 0
    if args.admin_cmd == 'jd-upsert':
        jd_text = args.jd_text or args.jd
        if not jd_text and not args.jd_file:
            raise ValueError('missing_jd_file_or_jd_text')
        payload = {
            'jd_id': args.jd_id,
            'jd_name': args.jd_name or args.jd_role,
            'jd_role': args.jd_role,
            'jd_text': jd_text or Path(args.jd_file).read_text(encoding='utf-8'),
        }
        _dump(adapter.dispatch('openclaw.admin.jd.upsert', payload)); return 0
    if args.admin_cmd == 'domain-generate':
        jd_payload = _resolve_jd_payload(jd_id=args.jd_id, jd_file=args.jd_file, jd_text=args.jd_text or args.jd, jd_name=args.jd_name, jd_role=args.jd_role)
        if 'jd_id' not in jd_payload:
            jd_payload = adapter.dispatch('openclaw.admin.jd.upsert', jd_payload).get('item', {})
        _dump(adapter.dispatch('openclaw.admin.domain.generate', {'jd_id': jd_payload['jd_id']})); return 0
    if args.admin_cmd == 'resume-parse':
        if args.jd_id:
            jd = _load_jd(args.jd_id)
            jd_text = jd['jd_text']
        elif args.jd_text or args.jd:
            jd_text = args.jd_text or args.jd
        elif args.jd_file:
            jd_text = Path(args.jd_file).read_text(encoding='utf-8')
        else:
            raise ValueError('missing_jd_id_or_jd_text')
        _dump(adapter.dispatch('openclaw.admin.resume.parse', {'resume_file': args.resume_file, 'role_name': args.role, 'jd_text': jd_text, 'candidate_name': args.candidate_name})); return 0
    if args.admin_cmd == 'candidate-upsert':
        jd_payload = _resolve_jd_payload(jd_id=args.jd_id, jd_file=args.jd_file, jd_text=args.jd_text or args.jd, jd_name=args.jd_name or args.role, jd_role=args.role)
        payload = {'candidate_id': args.candidate_id, 'candidate_name': args.name, 'interview_role': args.role, 'resume_file': args.resume_file, 'scheduled_at': args.scheduled_at, 'enabled': args.enabled == 'true', **jd_payload}
        _dump(adapter.dispatch('openclaw.admin.candidate.upsert', payload)); return 0
    if args.admin_cmd == 'candidate-add-from-dialog':
        dialog_text = Path(args.dialog_file).read_text(encoding='utf-8')
        _dump(adapter.dispatch('openclaw.admin.candidate.add_from_dialog', {'dialog_text': dialog_text, 'resume_file': args.resume_file, 'candidate_id': args.candidate_id})); return 0
    if args.admin_cmd == 'candidate-bulk-update':
        updates: dict[str, Any] = {}
        if args.scheduled_at:
            updates['scheduled_at'] = args.scheduled_at
        if args.enable:
            updates['enabled'] = args.enable == 'true'
        _dump(adapter.dispatch('openclaw.admin.candidate.bulk_update', {'indices': args.indices or [], 'updates': updates})); return 0
    if args.admin_cmd == 'candidate-bulk-remove':
        _dump(adapter.dispatch('openclaw.admin.candidate.bulk_remove', {'indices': args.indices or []})); return 0
    if args.admin_cmd == 'candidate-remove':
        _dump(adapter.dispatch('openclaw.admin.candidate.remove', {'candidate_id': args.candidate_id})); return 0
    if args.admin_cmd == 'candidate-refresh':
        _dump(adapter.dispatch('openclaw.admin.candidate.refresh', {'candidate_id': args.candidate_id})); return 0
    raise SystemExit(2)


def run_interview(args: argparse.Namespace) -> int:
    adapter = _adapter()
    if args.interview_cmd == 'identify':
        _dump(adapter.dispatch('openclaw.interview.identify', {'candidate_name': args.candidate_name, 'candidate_id': args.candidate_id, 'session_id': args.session_id})); return 0
    if args.interview_cmd == 'begin':
        _dump(adapter.dispatch('openclaw.interview.begin', {'session_id': args.session_id})); return 0
    if args.interview_cmd == 'status':
        _dump(adapter.dispatch('openclaw.interview.status', {'session_id': args.session_id})); return 0
    if args.interview_cmd == 'next':
        _dump(adapter.dispatch('openclaw.interview.next', {'session_id': args.session_id})); return 0
    if args.interview_cmd == 'reply':
        _dump(adapter.dispatch('openclaw.interview.reply', {'session_id': args.session_id, 'candidate_message': args.candidate_message})); return 0
    if args.interview_cmd == 'case-generate':
        _dump(adapter.dispatch('openclaw.interview.case_generate', {'session_id': args.session_id})); return 0
    if args.interview_cmd == 'finish':
        _dump(adapter.dispatch('openclaw.interview.finish', {'session_id': args.session_id})); return 0
    raise SystemExit(2)


def run_doctor(json_mode: bool = False) -> int:
    root = _root()
    cfg = load_config(root)
    storage = Storage(root, rag_root=cfg.paths.rag_root, workspace_root=cfg.paths.workspace_root)
    checks = {
        'config_exists': (root / 'config.yaml').exists(),
        'entrypoint_manifest_exists': (root / 'ENTRYPOINT.json').exists(),
        'entrypoint_exists': (root / 'openclaw-interviewer').exists(),
        'candidate_agent_exists': (root / '.agent/candidate/AGENTS.md').exists(),
        'admin_agent_exists': (root / '.agent/admin/AGENTS.md').exists(),
        'skill_exists': (root / 'SKILL.md').exists(),
        'workflows_dir_exists': (root / 'workflows').exists(),
        'rag_dir_exists': storage.rag_dir.exists(),
        'workspace_dir_exists': storage.workspace.exists(),
        'candidate_registry_exists': (storage.rag_dir / 'candidates/candidate.jsonl').exists(),
        'admin_bin_exists': (root / 'bin/admin').exists(),
        'interview_bin_exists': (root / 'bin/interview').exists(),
        'harness_bin_exists': (root / 'bin/harness').exists(),
    }
    ok = all(checks.values())
    payload = {'ok': ok, 'root': str(root), 'checks': checks}
    if json_mode:
        _dump(payload)
    else:
        print('== interviewer skill doctor ==')
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def run_harness(args: argparse.Namespace) -> int:
    from interviewer.harness import SkillHarness, dump_harness_result
    harness = SkillHarness(_root())
    result = harness.run(args.scenario, transcript_file=args.transcript_file)
    print(dump_harness_result(result, args.output))
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.lane == 'setup':
        from interviewer.setup_wizard import run_setup
        raise SystemExit(run_setup(_root()))
    if args.lane == 'admin':
        raise SystemExit(run_admin(args))
    if args.lane == 'interview':
        raise SystemExit(run_interview(args))
    if args.lane == 'doctor':
        raise SystemExit(run_doctor(args.json))
    if args.lane == 'harness':
        raise SystemExit(run_harness(args))
    raise SystemExit(2)


if __name__ == '__main__':
    main()
