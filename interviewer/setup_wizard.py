from __future__ import annotations

from pathlib import Path

from interviewer.config.loader import initialize_default_config, load_config
from interviewer.storage.store import Storage
from interviewer.skill_cmd import run_doctor


ENTRYPOINT_NAME = 'openclaw-interviewer'
ENTRYPOINT_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"
exec python3 -m interviewer.skill_cmd "$@"
"""


def ensure_command_entry(root: Path) -> tuple[Path, str]:
    entry = root / ENTRYPOINT_NAME
    desired = ENTRYPOINT_TEMPLATE
    if not entry.exists():
        entry.write_text(desired, encoding='utf-8')
        entry.chmod(0o755)
        return entry, 'created'
    current = entry.read_text(encoding='utf-8')
    if current != desired:
        entry.write_text(desired, encoding='utf-8')
        entry.chmod(0o755)
        return entry, 'updated'
    mode = entry.stat().st_mode
    if mode & 0o111 == 0:
        entry.chmod(mode | 0o755)
        return entry, 'fixed-permissions'
    return entry, 'ok'


def run_setup(root: str | Path) -> int:
    root = Path(root)
    entry, entry_status = ensure_command_entry(root)
    print('== OpenClaw Interviewer Setup ==')
    result = initialize_default_config(root)
    current = load_config(root)
    storage = Storage(root, rag_root=current.paths.rag_root, workspace_root=current.paths.workspace_root)
    print(f"配置文件已写入: {result['config_file']}")
    print(f"Skill 根目录: {root}")
    print(f"命令入口声明: {root / 'ENTRYPOINT.json'}")
    print(f"统一命令入口: {entry} ({entry_status})")
    print(f"候选人侧 Agent: {root / '.agent/candidate'}")
    print(f"管理员侧 Agent: {root / '.agent/admin'}")
    print(f"RAG 目录: {storage.rag_dir}")
    print(f"Workspace 目录: {storage.workspace}")
    print('后续统一通过以下命令名执行：')
    print(f"- {ENTRYPOINT_NAME} doctor")
    print(f"- {ENTRYPOINT_NAME} admin ...")
    print(f"- {ENTRYPOINT_NAME} interview ...")
    print(f"- {ENTRYPOINT_NAME} harness ...")
    print('执行一次健康检查：')
    rc = run_doctor(json_mode=False)
    print('推荐的后续命令：')
    print(f"1. {ENTRYPOINT_NAME} admin capabilities-list")
    print(f"2. {ENTRYPOINT_NAME} admin candidate-list")
    print(f"3. {ENTRYPOINT_NAME} admin candidate-initialize")
    print(f"4. {ENTRYPOINT_NAME} harness --scenario admin_ops")
    print(f"5. {ENTRYPOINT_NAME} harness --scenario full_interview")
    return rc

if __name__ == '__main__':
    raise SystemExit(run_setup(Path(__file__).resolve().parents[1]))
