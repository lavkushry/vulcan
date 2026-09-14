"""
Lightweight, pure-Python YAML parser fallback for AgentOS.
Parses Ansible meta/main.yml, defaults/main.yml, tasks/main.yml, and playbooks
without external dependencies (e.g. PyYAML).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union


def _strip_comment(line: str) -> str:
    """Strips comments while respecting single and double quoted strings."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == '#' and not in_single and not in_double:
            return line[:i]
    return line


def _parse_scalar(val: str) -> Any:
    val = val.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    lower = val.lower()
    if lower in ("true", "yes", "on"):
        return True
    if lower in ("false", "no", "off"):
        return False
    if lower in ("null", "none", "~"):
        return None
    if val == "[]":
        return []
    if val == "{}":
        return {}
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        parts = [p.strip() for p in inner.split(",")]
        return [_parse_scalar(p) for p in parts if p]
    if val.startswith("{") and val.endswith("}"):
        inner = val[1:-1].strip()
        if not inner:
            return {}
        res = {}
        for part in inner.split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                res[str(_parse_scalar(k))] = _parse_scalar(v)
        return res
    try:
        if "." in val or ("e" in val.lower() and not val.startswith("0x")):
            return float(val)
        return int(val)
    except ValueError:
        pass
    return val


def parse_yaml(text: str) -> Any:
    """Parses a YAML string into Python primitives (dict, list, scalar).
    
    If PyYAML is installed, delegates to yaml.safe_load.
    Otherwise uses an indentation-based recursive descent parser.
    """
    try:
        import yaml
        return yaml.safe_load(text)
    except (ImportError, ModuleNotFoundError):
        pass

    raw_lines = text.splitlines()
    cleaned_lines: List[Tuple[int, str]] = []
    for raw_line in raw_lines:
        line = _strip_comment(raw_line).rstrip()
        stripped = line.strip()
        if not stripped or stripped in ("---", "..."):
            continue
        indent = len(line) - len(line.lstrip(" "))
        cleaned_lines.append((indent, stripped))

    if not cleaned_lines:
        return {}

    def _parse_block(start_idx: int, min_indent: int) -> Tuple[Any, int]:
        idx = start_idx
        if idx >= len(cleaned_lines):
            return {}, idx

        first_indent, first_content = cleaned_lines[idx]
        is_list = first_content.startswith("- ") or first_content == "-"

        if is_list:
            items: List[Any] = []
            while idx < len(cleaned_lines):
                indent, content = cleaned_lines[idx]
                if indent < min_indent:
                    break
                if indent == min_indent and (content.startswith("- ") or content == "-"):
                    item_text = content[2:].strip() if content.startswith("- ") else ""
                    idx += 1
                    if not item_text:
                        # Value starts on next line with greater indent
                        if idx < len(cleaned_lines) and cleaned_lines[idx][0] > indent:
                            sub_val, idx = _parse_block(idx, cleaned_lines[idx][0])
                            items.append(sub_val)
                        else:
                            items.append(None)
                    elif ":" in item_text and not item_text.endswith(":"):
                        # Inline key-value pair, e.g. - name: EL
                        k, _, v = item_text.partition(":")
                        key = _parse_scalar(k)
                        val = _parse_scalar(v)
                        obj: Dict[str, Any] = {str(key): val}
                        # Check if child lines follow at greater indent
                        while idx < len(cleaned_lines) and cleaned_lines[idx][0] > indent:
                            child_indent, child_content = cleaned_lines[idx]
                            if ":" in child_content and not child_content.startswith("- "):
                                ck, _, cv = child_content.partition(":")
                                ckey = str(_parse_scalar(ck))
                                cval_str = cv.strip()
                                idx += 1
                                if cval_str:
                                    obj[ckey] = _parse_scalar(cval_str)
                                else:
                                    if idx < len(cleaned_lines) and cleaned_lines[idx][0] > child_indent:
                                        sub_child, idx = _parse_block(idx, cleaned_lines[idx][0])
                                        obj[ckey] = sub_child
                                    else:
                                        obj[ckey] = None
                            elif child_content.startswith("- "):
                                break
                            else:
                                idx += 1
                        items.append(obj)
                    elif item_text.endswith(":"):
                        # - key:
                        key = str(_parse_scalar(item_text[:-1]))
                        if idx < len(cleaned_lines) and cleaned_lines[idx][0] > indent:
                            sub_val, idx = _parse_block(idx, cleaned_lines[idx][0])
                            items.append({key: sub_val})
                        else:
                            items.append({key: None})
                    else:
                        items.append(_parse_scalar(item_text))
                elif indent > min_indent:
                    idx += 1
                else:
                    break
            return items, idx
        else:
            mapping: Dict[str, Any] = {}
            while idx < len(cleaned_lines):
                indent, content = cleaned_lines[idx]
                if indent < min_indent:
                    break
                if indent == min_indent:
                    if ":" in content and not content.startswith("- "):
                        k, _, v = content.partition(":")
                        key = str(_parse_scalar(k))
                        val_str = v.strip()
                        idx += 1
                        if val_str:
                            mapping[key] = _parse_scalar(val_str)
                        else:
                            if idx < len(cleaned_lines) and cleaned_lines[idx][0] > indent:
                                sub_val, idx = _parse_block(idx, cleaned_lines[idx][0])
                                mapping[key] = sub_val
                            else:
                                mapping[key] = None
                    else:
                        idx += 1
                elif indent > min_indent:
                    idx += 1
                else:
                    break
            return mapping, idx

    parsed, _ = _parse_block(0, cleaned_lines[0][0])
    return parsed
