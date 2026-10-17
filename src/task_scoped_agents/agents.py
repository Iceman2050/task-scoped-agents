"""
Two mock agents for demonstrating and testing enforcement.

* ``MockCompliantAgent`` - only calls tools inside its task's grant.
* ``MockAdversarialAgent`` - first does legitimate in-scope work, then tries
  to reach tools outside its grant (``shell_exec`` is registered but not
  granted; ``exfiltrate`` is not even registered).

Both agents receive ONLY a ScopedExecutor -- they never see the raw registry.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .enforcement import ScopedExecutor, ScopeDeniedError


class MockCompliantAgent:
    """A well-behaved agent: stays inside its task's declared scope."""

    name = "mock-compliant"

    def run(self, executor: ScopedExecutor, task_id: str) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for tool_name in executor.allowed[:2]:  # do real in-scope work
            output = executor.call_tool(tool_name, query="task-scoped agents")
            results.append({"tool": tool_name, "output": output})
        return {
            "agent": self.name,
            "task_id": task_id,
            "calls": results,
            "denials": 0,
        }


class MockAdversarialAgent:
    """A rogue agent: attempts out-of-scope tool calls mid-task."""

    name = "mock-adversarial"

    # Probes it attempts after its legitimate work. shell_exec exists in the
    # demo registry but is outside every task grant; exfiltrate does not exist.
    PROBES = ("shell_exec", "exfiltrate")

    def run(self, executor: ScopedExecutor, task_id: str) -> Dict[str, Any]:
        allowed_calls: List[str] = []
        denied: List[Dict[str, str]] = []

        if executor.allowed:
            output = executor.call_tool(executor.allowed[0], query="task-scoped agents")
            allowed_calls.append(f"{executor.allowed[0]} -> {output!r}"[:80])

        for probe in self.PROBES:
            try:
                executor.call_tool(probe, command="whoami")
            except ScopeDeniedError as exc:
                denied.append(
                    {
                        "tool": probe,
                        "reason": exc.event.reason,
                        "timestamp": exc.event.timestamp,
                    }
                )

        return {
            "agent": self.name,
            "task_id": task_id,
            "allowed_calls": allowed_calls,
            "denials": denied,
        }


AGENTS = {
    MockCompliantAgent.name: MockCompliantAgent,
    MockAdversarialAgent.name: MockAdversarialAgent,
}
