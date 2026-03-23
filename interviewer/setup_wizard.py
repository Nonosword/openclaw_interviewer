from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from interviewer.config.loader import initialize_default_config, load_config
from interviewer.storage.store import Storage
from interviewer.skill_cmd import run_doctor


ENTRYPOINT_NAME = 'openclaw-interviewer'
VENV_DIRNAME = '.venv'
ENTRYPOINT_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  "$SCRIPT_DIR/setup"
fi
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Project bootstrap failed while creating $PYTHON_BIN." >&2
  exit 1
fi
exec "$PYTHON_BIN" -m interviewer.skill_cmd "$@"
"""

COMPAT_ENTRYPOINTS = {
    'bin/admin': 'admin',
    'bin/interview': 'interview',
    'bin/doctor': 'doctor',
    'bin/harness': 'harness',
}

AGENT_SPECS = [
    {
        'name': 'openclaw-interviewer',
        'workspace': '~/.openclaw/workspace_interviewer/candidate',
        'source_docs': '.agent/candidate',
    },
    {
        'name': 'openclaw-interviewer-admin',
        'workspace': '~/.openclaw/workspace_interviewer/admin',
        'source_docs': '.agent/admin',
    },
]


def compat_entrypoint_template(subcommand: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$SCRIPT_DIR:${{PYTHONPATH:-}}"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  "$SCRIPT_DIR/setup"
fi
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Project bootstrap failed while creating $PYTHON_BIN." >&2
  exit 1
fi
exec "$PYTHON_BIN" -m interviewer.skill_cmd {subcommand} "$@"
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


def ensure_compat_entry(root: Path, relative_path: str, subcommand: str) -> tuple[Path, str]:
    path = root / relative_path
    desired = compat_entrypoint_template(subcommand)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desired, encoding='utf-8')
        path.chmod(0o755)
        return path, 'created'
    current = path.read_text(encoding='utf-8')
    if current != desired:
        path.write_text(desired, encoding='utf-8')
        path.chmod(0o755)
        return path, 'updated'
    mode = path.stat().st_mode
    if mode & 0o111 == 0:
        path.chmod(mode | 0o755)
        return path, 'fixed-permissions'
    return path, 'ok'


def ensure_virtualenv(root: Path) -> tuple[Path, str]:
    venv_dir = root / VENV_DIRNAME
    python_bin = venv_dir / 'bin' / 'python'
    if python_bin.exists():
        return venv_dir, 'ok'
    proc = subprocess.run(
        [sys.executable, '-m', 'venv', '--system-site-packages', str(venv_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or 'venv_creation_failed')
    return venv_dir, 'created'


def list_openclaw_agents() -> list[dict]:
    proc = subprocess.run(
        ['openclaw', 'agents', 'list', '--json'],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or 'openclaw_agents_list_failed')
    return json.loads(proc.stdout or '[]')


def ensure_openclaw_agent(name: str, workspace: Path) -> dict[str, str]:
    workspace = workspace.expanduser().resolve()
    agents = list_openclaw_agents()
    by_name = next((item for item in agents if item.get('name') == name), None)
    if by_name:
        existing_workspace = Path(str(by_name.get('workspace') or '')).expanduser().resolve()
        if existing_workspace == workspace:
            return {'status': 'skipped', 'agent': name, 'workspace': str(workspace)}
        return {
            'status': 'conflict',
            'agent': name,
            'workspace': str(workspace),
            'existing_workspace': str(existing_workspace),
        }
    proc = subprocess.run(
        ['openclaw', 'agents', 'add', name, '--workspace', str(workspace), '--non-interactive', '--json'],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f'openclaw_agent_add_failed:{name}')
    return {'status': 'created', 'agent': name, 'workspace': str(workspace)}


def sync_agent_docs(root: Path, source_dir: str, target_workspace: Path) -> dict[str, str | int]:
    src = root / source_dir
    target = target_workspace.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in src.glob('*.md'):
        shutil.copy2(path, target / path.name)
        copied += 1
    return {'workspace': str(target), 'copied': copied}


def run_setup(root: str | Path) -> int:
    root = Path(root)
    print('== OpenClaw Interviewer Setup ==')
    result = initialize_default_config(root)
    current = load_config(root)
    storage = Storage(root, rag_root=current.paths.rag_root, workspace_root=current.paths.workspace_root)
    venv_dir, venv_status = ensure_virtualenv(root)
    entry, entry_status = ensure_command_entry(root)
    compat_statuses = [ensure_compat_entry(root, rel, subcommand) for rel, subcommand in COMPAT_ENTRYPOINTS.items()]
    agent_results = []
    sync_results = []
    for spec in AGENT_SPECS:
        workspace = Path(spec['workspace']).expanduser()
        agent_result = ensure_openclaw_agent(spec['name'], workspace)
        agent_results.append(agent_result)
        if agent_result['status'] != 'conflict':
            sync_results.append(sync_agent_docs(root, spec['source_docs'], workspace))
    print(f"配置文件已写入: {result['config_file']}")
    print(f"Skill 根目录: {root}")
    print(f"命令入口声明: {root / 'ENTRYPOINT.json'}")
    print(f"Python 虚拟环境: {venv_dir} ({venv_status})")
    print(f"统一命令入口: {entry} ({entry_status})")
    for compat_path, compat_status in compat_statuses:
        print(f"兼容命令入口: {compat_path} ({compat_status})")
    print(f"候选人侧 Agent: {root / '.agent/candidate'}")
    print(f"管理员侧 Agent: {root / '.agent/admin'}")
    for item in agent_results:
        line = f"OpenClaw agent {item['agent']}: {item['status']} -> {item['workspace']}"
        if item.get('existing_workspace'):
            line += f" (existing: {item['existing_workspace']})"
        print(line)
    for item in sync_results:
        print(f"同步 Agent docs -> {item['workspace']} (copied={item['copied']})")
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
