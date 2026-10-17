"""
Enforcement wrapper: the agent physically cannot call a tool outside its
current task's declared scope.

Every tool call the agent makes goes through ``ScopedExecutor.call_tool``.
In-scope calls run. Out-of-scope calls are denied BEFORE the tool function is
invoked, raise :class:`ScopeDeniedError`, and append an auditable denial event
to a JSONL log::

    {"task_id": "...", "tool_name": "...", "timestamp": "...Z",
     "reason": "out_of_scope"}

Denial reasons:
    * ``unknown_task``   - no grant exists for the task id
    * ``unknown_tool``   - the registry has no such tool
    * ``out_of_scope``   - tool exists but the task's grant does not list it
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from .grants import GrantStore
from .registry import ToolRegistry


@dataclass
class DenialEvent:
    task_id: str
    tool_name: str
    timestamp: str  # UTC ISO-8601
    reason: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class ScopeDeniedError(Exception):
    """Raised when a tool call falls outside the task's declared scope."""

    def __init__(self, event: DenialEvent) -> None:
        self.event = event
        super().__init__(
            f"scope denied: task '{event.task_id}' may not call tool "
            f"'{event.tool_name}' (reason: {event.reason})"
        )


class ScopedExecutor:
    """
    Wraps an agent's tool-call path with a per-task capability check.

    Parameters
    ----------
    task_id:
        The task the agent is currently executing. Its grant is the allowlist.
    grants:
        A :class:`GrantStore` loaded from tasks.yaml.
    registry:
        A :class:`ToolRegistry` holding the real tool implementations.
    audit_log:
        Path of the JSONL denial audit log. Denials are APPENDED, one
        event per line, and the file is created on first denial.

    Usage with a real framework: give the agent only this executor for tool
    calls -- never hand it the raw registry.
    """

    def __init__(
        self,
        task_id: str,
        grants: GrantStore,
        registry: ToolRegistry,
        audit_log: str = "denials.jsonl",
    ) -> None:
        self.task_id = task_id
        self.grants = grants
        self.registry = registry
        self.audit_log = audit_log
        self.allowed: List[str] = sorted(grants.tools_for(task_id))

    def is_allowed(self, tool_name: str) -> bool:
        return (
            self.grants.get(self.task_id) is not None
            and tool_name in self.grants.tools_for(self.task_id)
        )

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Run *tool_name* if it is in scope; otherwise deny + log + raise."""
        if self.grants.get(self.task_id) is None:
            self._deny(tool_name, "unknown_task")
        if not self.registry.has(tool_name):
            self._deny(tool_name, "unknown_tool")
        if not self.is_allowed(tool_name):
            self._deny(tool_name, "out_of_scope")
        tool = self.registry.get(tool_name)
        return tool(**kwargs)

    def _deny(self, tool_name: str, reason: str) -> None:
        event = DenialEvent(
            task_id=self.task_id,
            tool_name=tool_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )
        with open(self.audit_log, "a", encoding="utf-8") as fh:
            fh.write(event.to_json() + "\n")
        raise ScopeDeniedError(event)


def read_denials(audit_log: str = "denials.jsonl") -> List[Dict[str, Any]]:
    """Read denial events back from a JSONL audit log."""
    events: List[Dict[str, Any]] = []
    try:
        with open(audit_log, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except FileNotFoundError:
        pass
    return events
