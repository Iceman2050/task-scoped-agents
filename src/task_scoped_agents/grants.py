"""
Grant model: each task declares exactly which tools it may call.

`tasks.yaml` shape (subset of YAML — indented mappings and lists only):

    tasks:
      research-agent:
        description: "Summarize a topic from public sources"
        tools: [web_search, read_file, summarize]
      code-agent:
        description: "Read and test local code"
        tools:
          - read_file
          - run_tests

A grant is an allowlist. There is no wildcard, no inheritance, no "all tools".
If a tool is not listed for the task, calling it is denied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskGrant:
    task_id: str
    tools: List[str] = field(default_factory=list)
    description: str = ""


class GrantError(ValueError):
    """Raised when tasks.yaml cannot be parsed into a grant model."""


def _strip_comment(line: str) -> str:
    # Naive comment stripper: fine for our restricted grammar.
    if "#" in line:
        in_sq = in_dq = False
        for i, ch in enumerate(line):
            if ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == "#" and not in_sq and not in_dq:
                return line[:i]
        return line
    return line


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_flow_list(value: str) -> List[str]:
    inner = value.strip()[1:-1].strip()
    if not inner:
        return []
    return [_unquote(item) for item in inner.split(",") if item.strip()]


class GrantStore:
    """Loads and holds the task -> allowed-tools grant model from a file."""

    def __init__(self, tasks: Dict[str, TaskGrant]) -> None:
        self.tasks: Dict[str, TaskGrant] = tasks

    @classmethod
    def load(cls, path: str) -> "GrantStore":
        """Parse *path* (tasks.yaml) and return a GrantStore. Fresh call = fresh scope."""
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        tasks = _parse(lines, path)
        return cls(tasks)

    def get(self, task_id: str) -> Optional[TaskGrant]:
        return self.tasks.get(task_id)

    def tools_for(self, task_id: str) -> List[str]:
        grant = self.get(task_id)
        return list(grant.tools) if grant else []

    def task_ids(self) -> List[str]:
        return list(self.tasks.keys())


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse(lines, path: str) -> Dict[str, TaskGrant]:
    tasks: Dict[str, TaskGrant] = {}
    current_task: Optional[str] = None
    current_key: Optional[str] = None
    pending_list: Optional[List[str]] = None
    seen_root = False

    def flush_list():
        nonlocal pending_list, current_key
        if current_task is not None and pending_list is not None:
            grant = tasks[current_task]
            if current_key == "tools":
                grant.tools = list(pending_list)
        pending_list = None

    for lineno, raw in enumerate(lines, start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = _indent_of(line)
        content = line.strip()

        if indent == 0:
            flush_list()
            if content != "tasks:":
                raise GrantError(f"{path}:{lineno}: expected top-level 'tasks:'")
            seen_root = True
            continue
        if not seen_root:
            raise GrantError(f"{path}:{lineno}: content before 'tasks:'")

        if content.startswith("- "):
            # Block list item belongs to the pending key of the current task
            # (tasks: 0, task id: 2, key: 4, list item: 6).
            if indent != 6 or current_task is None or current_key is None:
                raise GrantError(f"{path}:{lineno}: unexpected list item")
            if pending_list is None:
                pending_list = []
            pending_list.append(_unquote(content[2:]))
            continue

        flush_list()

        if indent == 2 and content.endswith(":") and " " not in content[:-1]:
            # New task id.
            current_task = _unquote(content[:-1])
            if not current_task:
                raise GrantError(f"{path}:{lineno}: empty task id")
            if current_task in tasks:
                raise GrantError(f"{path}:{lineno}: duplicate task id '{current_task}'")
            tasks[current_task] = TaskGrant(task_id=current_task)
            current_key = None
            continue

        if indent == 4 and ":" in content and current_task is not None:
            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip()
            grant = tasks[current_task]
            if key == "tools":
                current_key = "tools"
                if value.startswith("["):
                    grant.tools = _parse_flow_list(value)
                    current_key = None
                elif value:
                    raise GrantError(f"{path}:{lineno}: 'tools' must be a list")
                # empty value -> block list follows
            elif key == "description":
                grant.description = _unquote(value)
                current_key = None
            else:
                raise GrantError(f"{path}:{lineno}: unknown key '{key}' (allowed: tools, description)")
            continue

        raise GrantError(f"{path}:{lineno}: cannot parse line: {raw!r}")

    flush_list()
    return tasks
