from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from interviewer.api.adapter import OpenClawAdapter
from interviewer.harness import SkillHarness, dump_harness_result
from interviewer.storage.store import Storage


def _run_setup(root: Path) -> int:
    return subprocess.run(['/bin/sh', str(root / 'setup')], check=False).returncode


def _resolve_jd_payload(root: Path, *, jd_id: str | None, jd_file: str | None, jd_text: str | None, jd_name: str | None, jd_role: str | None) -> dict:
    if jd_id:
        return {'jd_id': jd_id}
    if jd_text:
        return {'jd_name': jd_name or jd_role, 'jd_role': jd_role, 'jd_text': jd_text}
    if not jd_file:
        raise ValueError('missing_jd_id_or_jd_text')
    return {'jd_name': jd_name or jd_role, 'jd_role': jd_role, 'jd_text': Path(jd_file).read_text(encoding='utf-8')}


def _load_jd(root: Path, jd_id: str) -> dict:
    storage = Storage(root)
    for row in storage.read_jsonl(storage.jd_path):
        if row.get('jd_id') == jd_id:
            return row
    raise ValueError('jd_not_found')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='interviewer')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('setup')
    sub.add_parser('config-show')
    sub.add_parser('init-candidates')
    sub.add_parser('list-capabilities')
    sub.add_parser('list-jds')
    p_jd = sub.add_parser('upsert-jd')
    p_jd.add_argument('--jd-id')
    p_jd.add_argument('--jd-name')
    p_jd.add_argument('--jd-role', required=True)
    p_jd.add_argument('--jd-file')
    p_jd.add_argument('--jd-text')
    p_jd.add_argument('--jd')
    p_domain = sub.add_parser('build-domain')
    p_domain.add_argument('--jd-id')
    p_domain.add_argument('--jd-name')
    p_domain.add_argument('--jd-role')
    p_domain.add_argument('--jd-file')
    p_domain.add_argument('--jd-text')
    p_domain.add_argument('--jd')
    p_upsert = sub.add_parser('upsert-candidate')
    p_upsert.add_argument('--candidate-id', required=True)
    p_upsert.add_argument('--name', required=True)
    p_upsert.add_argument('--role', required=True)
    p_upsert.add_argument('--jd-id')
    p_upsert.add_argument('--jd-name')
    p_upsert.add_argument('--jd-file')
    p_upsert.add_argument('--jd-text')
    p_upsert.add_argument('--jd')
    p_upsert.add_argument('--resume-file', required=True)
    p_upsert.add_argument('--scheduled-at', required=True)
    p_add = sub.add_parser('add-candidate-dialog')
    p_add.add_argument('--dialog-file', required=True)
    p_add.add_argument('--resume-file')
    p_add.add_argument('--candidate-id')
    p_bulk = sub.add_parser('bulk-update-candidates')
    p_bulk.add_argument('--indices', nargs='*', type=int)
    p_bulk.add_argument('--scheduled-at')
    p_bulk.add_argument('--enable', choices=['true','false'])
    p_remove = sub.add_parser('bulk-remove-candidates')
    p_remove.add_argument('--indices', nargs='*', type=int)
    p_del = sub.add_parser('remove-candidate')
    p_del.add_argument('--candidate-id', required=True)
    p_refresh = sub.add_parser('refresh-candidate')
    p_refresh.add_argument('--candidate-id', required=True)
    sub.add_parser('parse-resumes')
    sub.add_parser('list-candidates')
    sub.add_parser('inspect-rag')
    sub.add_parser('demo-interview')
    p_harness = sub.add_parser('skill-harness')
    p_harness.add_argument('--scenario', default='full_interview', choices=['identify_only','full_interview','security_probe','transcript_replay','admin_ops'])
    p_harness.add_argument('--transcript-file')
    p_harness.add_argument('--output')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    adapter = OpenClawAdapter(root)
    if args.command == 'setup':
        raise SystemExit(_run_setup(root))
    if args.command == 'config-show':
        print(adapter.dispatch('openclaw.admin.config.show', {})); return
    if args.command == 'init-candidates':
        print(adapter.dispatch('openclaw.admin.candidate.initialize', {})); return
    if args.command == 'list-capabilities':
        print(adapter.dispatch('openclaw.admin.capabilities.list', {})); return
    if args.command == 'list-jds':
        print(adapter.dispatch('openclaw.admin.jd.list', {})); return
    if args.command == 'upsert-jd':
        jd_text = args.jd_text or args.jd
        if not jd_text and not args.jd_file:
            raise ValueError('missing_jd_file_or_jd_text')
        print(adapter.dispatch('openclaw.admin.jd.upsert', {'jd_id': args.jd_id, 'jd_name': args.jd_name or args.jd_role, 'jd_role': args.jd_role, 'jd_text': jd_text or Path(args.jd_file).read_text(encoding='utf-8')})); return
    if args.command == 'build-domain':
        jd_payload = _resolve_jd_payload(root, jd_id=args.jd_id, jd_file=args.jd_file, jd_text=args.jd_text or args.jd, jd_name=args.jd_name, jd_role=args.jd_role)
        if 'jd_id' not in jd_payload:
            jd_payload = adapter.dispatch('openclaw.admin.jd.upsert', jd_payload)['item']
        print(adapter.dispatch('openclaw.admin.domain.generate', {'jd_id': jd_payload['jd_id']})); return
    if args.command == 'upsert-candidate':
        jd_payload = _resolve_jd_payload(root, jd_id=args.jd_id, jd_file=args.jd_file, jd_text=args.jd_text or args.jd, jd_name=args.jd_name or args.role, jd_role=args.role)
        print(adapter.dispatch('openclaw.admin.candidate.upsert', {'candidate_id': args.candidate_id, 'candidate_name': args.name, 'interview_role': args.role, 'resume_file': args.resume_file, 'scheduled_at': args.scheduled_at, 'enabled': True, **jd_payload})); return
    if args.command == 'add-candidate-dialog':
        dialog_text = Path(args.dialog_file).read_text(encoding='utf-8')
        print(adapter.dispatch('openclaw.admin.candidate.add_from_dialog', {'dialog_text': dialog_text, 'resume_file': args.resume_file, 'candidate_id': args.candidate_id})); return
    if args.command == 'bulk-update-candidates':
        updates = {}
        if args.scheduled_at:
            updates['scheduled_at'] = args.scheduled_at
        if args.enable:
            updates['enabled'] = (args.enable == 'true')
        print(adapter.dispatch('openclaw.admin.candidate.bulk_update', {'indices': args.indices or [], 'updates': updates})); return
    if args.command == 'bulk-remove-candidates':
        print(adapter.dispatch('openclaw.admin.candidate.bulk_remove', {'indices': args.indices or []})); return
    if args.command == 'remove-candidate':
        print(adapter.dispatch('openclaw.admin.candidate.remove', {'candidate_id': args.candidate_id})); return
    if args.command == 'refresh-candidate':
        print(adapter.dispatch('openclaw.admin.candidate.refresh', {'candidate_id': args.candidate_id})); return
    if args.command == 'parse-resumes':
        rows = adapter.dispatch('openclaw.admin.candidate.list', {}).get('items', [])
        for row in rows:
            jd = _load_jd(root, row['jd_id'])
            print(adapter.dispatch('openclaw.admin.resume.parse', {'resume_file': row['resume_file'], 'role_name': row['interview_role'], 'jd_text': jd['jd_text'], 'candidate_name': row['candidate_name']}))
        return
    if args.command == 'list-candidates':
        print(adapter.dispatch('openclaw.admin.candidate.list', {})); return
    if args.command == 'inspect-rag':
        print(adapter.dispatch('openclaw.admin.retrieval.inspect', {})); return
    if args.command == 'skill-harness':
        harness = SkillHarness(root)
        result = harness.run(args.scenario, transcript_file=args.transcript_file)
        print(dump_harness_result(result, args.output)); return
    if args.command == 'demo-interview':
        adapter.dispatch('openclaw.admin.candidate.initialize', {})
        identify = adapter.dispatch('openclaw.interview.identify', {'candidate_name': '张三', 'candidate_id': 'C2026001'})
        sid = identify['session_id']
        print(identify['visible_message'])
        print(adapter.dispatch('openclaw.interview.begin', {'session_id': sid})['visible_message'])
        action = adapter.dispatch('openclaw.interview.next', {'session_id': sid})
        steps = 0
        while steps < 40:
            print(action['visible_message'])
            if action.get('final'):
                break
            action = adapter.dispatch('openclaw.interview.reply', {'session_id': sid, 'candidate_message': '首先我会确认背景、目标和约束，然后通过日志、监控、指标、回滚和压测来分析问题，最后说明机制、取舍、风险与验证方式，并结合实际案例推进治理。'})
            if action.get('final') or action.get('action') == 'finish':
                print(action['visible_message'])
                break
            steps += 1
        return

if __name__ == '__main__':
    main()
