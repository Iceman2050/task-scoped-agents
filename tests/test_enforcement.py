"""Enforcement tests: the agent physically cannot reach outside its scope."""

import json
import os

import pytest

from task_scoped_agents import (
    GrantStore,
    ScopeDeniedError,
    ScopedExecutor,
    ToolRegistry,
)
from task_scoped_agents.enforcement import read_denials


def make_executor(tmp_path, yaml_text, task_id="research", audit_name="denials.jsonl"):
    tasks_file = tmp_path / "tasks.yaml"
    tasks_file.write_text(yaml_text, encoding="utf-8")
    grants = GrantStore.load(str(tasks_file))

    registry = ToolRegistry()
    executed = []

    def record(name):
        def fn(**kwargs):
            executed.append(name)  # proof the tool body ran
            return f"{name}-ok"

        return fn

    for name in ("web_search", "read_file", "summarize", "shell_exec"):
        registry.register(name, record(name))

    executor = ScopedExecutor(
        task_id=task_id,
        grants=grants,
        registry=registry,
        audit_log=str(tmp_path / audit_name),
    )
    return executor, executed, tmp_path / audit_name


RESEARCH_YAML = """tasks:
  research:
    description: "Summarize a topic"
    tools:
      - web_search
      - read_file
      - summarize
"""


def test_out_of_scope_call_is_denied_and_tool_never_executes(tmp_path):
    executor, executed, _ = make_executor(tmp_path, RESEARCH_YAML)
    with pytest.raises(ScopeDeniedError):
        executor.call_tool("shell_exec", command="whoami")
    assert executed == [], "out-of-scope tool body must never run"


def test_in_scope_call_is_allowed_and_executes(tmp_path):
    executor, executed, _ = make_executor(tmp_path, RESEARCH_YAML)
    result = executor.call_tool("web_search", query="agents")
    assert result == "web_search-ok"
    assert executed == ["web_search"]


def test_denial_is_logged_with_task_id_and_timestamp(tmp_path):
    executor, _, audit_file = make_executor(tmp_path, RESEARCH_YAML)
    with pytest.raises(ScopeDeniedError):
        executor.call_tool("shell_exec", command="whoami")
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["task_id"] == "research"
    assert event["tool_name"] == "shell_exec"
    assert event["reason"] == "out_of_scope"
    assert event["timestamp"], "denial must carry a timestamp"
    # timestamp must be parseable
    from datetime import datetime

    datetime.fromisoformat(event["timestamp"])


def test_grant_reload_enforces_new_scope(tmp_path):
    tasks_file = tmp_path / "tasks.yaml"
    tasks_file.write_text(RESEARCH_YAML, encoding="utf-8")

    registry = ToolRegistry()
    executed = []
    for name in ("web_search", "shell_exec"):
        registry.register(name, lambda n=name, **kw: executed.append(n) or f"{n}-ok")

    def scoped(task_id):
        return ScopedExecutor(task_id, GrantStore.load(str(tasks_file)), registry,
                              audit_log=str(tmp_path / "denials.jsonl"))

    # Before: shell_exec denied.
    with pytest.raises(ScopeDeniedError):
        scoped("research").call_tool("shell_exec", command="whoami")
    assert executed == []

    # Modify tasks.yaml, reload, new scope enforced.
    tasks_file.write_text(
        """tasks:
  research:
    tools: [web_search, shell_exec]
""",
        encoding="utf-8",
    )
    result = scoped("research").call_tool("shell_exec", command="whoami")
    assert result == "shell_exec-ok"
    assert executed == ["shell_exec"]


def test_unknown_tool_is_denied(tmp_path):
    executor, executed, audit_file = make_executor(tmp_path, RESEARCH_YAML)
    with pytest.raises(ScopeDeniedError) as excinfo:
        executor.call_tool("exfiltrate")
    assert excinfo.value.event.reason == "unknown_tool"
    assert executed == []
    assert read_denials(str(audit_file))[0]["reason"] == "unknown_tool"


def test_unknown_task_is_denied(tmp_path):
    executor, executed, _ = make_executor(tmp_path, RESEARCH_YAML, task_id="nope")
    with pytest.raises(ScopeDeniedError) as excinfo:
        executor.call_tool("web_search")
    assert excinfo.value.event.reason == "unknown_task"
    assert executed == []


def test_audit_log_appends_jsonl(tmp_path):
    executor, _, audit_file = make_executor(tmp_path, RESEARCH_YAML)
    for tool in ("shell_exec", "exfiltrate"):
        with pytest.raises(ScopeDeniedError):
            executor.call_tool(tool)
    events = read_denials(str(audit_file))
    assert len(events) == 2
    assert {e["tool_name"] for e in events} == {"shell_exec", "exfiltrate"}
