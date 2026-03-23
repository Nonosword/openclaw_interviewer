from __future__ import annotations

import json
from typing import Any


def load_yaml_text(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return _parse_yaml(text)
    return yaml.safe_load(text) or {}


def dump_yaml_text(data: Any) -> str:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return _dump_yaml(data)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def _parse_yaml(text: str) -> Any:
    rows = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        rows.append((indent, raw.strip()))
    if not rows:
        return {}
    value, index = _parse_block(rows, 0, rows[0][0])
    if index != len(rows):
        raise ValueError('yaml_parse_incomplete')
    return value


def _parse_block(rows: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if rows[index][1].startswith('- '):
        return _parse_list(rows, index, indent)
    return _parse_dict(rows, index, indent)


def _parse_dict(rows: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(rows):
        row_indent, text = rows[index]
        if row_indent < indent:
            break
        if row_indent > indent:
            raise ValueError(f'unexpected_indent:{row_indent}')
        if text.startswith('- '):
            break
        key, sep, raw_value = text.partition(':')
        if not sep:
            raise ValueError(f'invalid_mapping:{text}')
        key = key.strip()
        raw_value = raw_value.strip()
        index += 1
        if raw_value:
            result[key] = _parse_scalar(raw_value)
            continue
        if index < len(rows) and rows[index][0] > indent:
            child, index = _parse_block(rows, index, rows[index][0])
            result[key] = child
        else:
            result[key] = {}
    return result, index


def _parse_list(rows: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(rows):
        row_indent, text = rows[index]
        if row_indent < indent:
            break
        if row_indent != indent or not text.startswith('- '):
            break
        item_text = text[2:].strip()
        index += 1
        if item_text:
            result.append(_parse_scalar(item_text))
            continue
        if index < len(rows) and rows[index][0] > indent:
            child, index = _parse_block(rows, index, rows[index][0])
            result.append(child)
        else:
            result.append(None)
    return result, index


def _parse_scalar(raw: str) -> Any:
    if raw in {'true', 'True'}:
        return True
    if raw in {'false', 'False'}:
        return False
    if raw in {'null', 'None', '~'}:
        return None
    if raw.isdigit() or (raw.startswith('-') and raw[1:].isdigit()):
        return int(raw)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        return raw[1:-1]
    return raw


def _dump_yaml(data: Any, indent: int = 0) -> str:
    lines = _dump_lines(data, indent)
    return '\n'.join(lines) + ('\n' if lines else '')


def _dump_lines(data: Any, indent: int) -> list[str]:
    prefix = ' ' * indent
    if isinstance(data, dict):
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f'{prefix}{key}:')
                lines.extend(_dump_lines(value, indent + 2))
            else:
                lines.append(f'{prefix}{key}: {_format_scalar(value)}')
        return lines
    if isinstance(data, list):
        lines = []
        for value in data:
            if isinstance(value, (dict, list)):
                lines.append(f'{prefix}-')
                lines.extend(_dump_lines(value, indent + 2))
            else:
                lines.append(f'{prefix}- {_format_scalar(value)}')
        return lines
    return [f'{prefix}{_format_scalar(data)}']


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return 'null'
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in [':', '#', '"']) or text != text.strip():
        return json.dumps(text, ensure_ascii=False)
    return text
