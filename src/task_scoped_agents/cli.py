"""CLI: run a mock agent under task-scoped enforcement, or print the audit log."""

from __future__ import annotations

import argparse
import json
import sys

from .agents import AGENTS
from .enforcement import ScopedExecutor, read_denials
from .grants import GrantStore
from .registry import ToolRegistry


def _demo_registry() -> ToolRegistry:
    """Demo tool implementations. shell_exec is registered but deliberately
    outside every grant in tasks.yaml -- the adversarial probe target."""
    registry = ToolRegistry()
    registry.register("web_search", lambda query: f"[search results for '{query}']")
    registry.register("read_file", lambda query: f"[contents of '{query}.md']")
    registry.register("summarize", lambda query: f"[summary of '{query}']")
    registry.register("run_tests", lambda query: "[12 passed, 0 failed]")
    registry.register("shell_exec", lambda command: f"[EXECUTED: {command}]")
    return registry


def cmd_run(args: argparse.Namespace) -> int:
    grants = GrantStore.load(args.tasks)
    if args.task_id not in grants.task_ids():
        print(f"error: unknown task '{args.task_id}'. Known: {', '.join(grants.task_ids())}",
              file=sys.stderr)
        return 2
    agent_cls = AGENTS[args.agent]
    executor = ScopedExecutor(
        task_id=args.task_id,
        grants=grants,
        registry=_demo_registry(),
        audit_log=args.audit_log,
    )
    report = agent_cls().run(executor, args.task_id)
    print(json.dumps(report, indent=2))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    events = read_denials(args.audit_log)
    if not events:
        print(f"No denial events in {args.audit_log}.")
        return 0
    for event in events:
        print(json.dumps(event))
    print(f"\n{len(events)} denial event(s) total.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="task-scoped-agents",
        description="Per-task capability tokens for AI agents: OAuth scopes, but for tool calls.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run a mock agent under enforcement.")
    p_run.add_argument("--tasks", required=True, help="Path to tasks.yaml (the grant model).")
    p_run.add_argument("--agent", required=True, choices=sorted(AGENTS),
                       help="Which mock agent to run.")
    p_run.add_argument("--task-id", required=True, help="Task whose grant scopes the run.")
    p_run.add_argument("--audit-log", default="denials.jsonl",
                       help="Where denial events are appended (JSONL).")
    p_run.set_defaults(func=cmd_run)

    p_audit = sub.add_parser("audit", help="Print the denial audit log.")
    p_audit.add_argument("--audit-log", default="denials.jsonl",
                         help="Denial audit log to read (JSONL).")
    p_audit.set_defaults(func=cmd_audit)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
