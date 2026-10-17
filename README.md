# task-scoped-agents

**Per-task capability tokens for AI agents — OAuth scopes, but for tool calls.**

## The problem

An AI agent typically holds every tool for the whole session — file system,
shell, network, secrets — but only needs two or three of them for the current
task. A compromised, buggy, or prompt-injected agent can reach the rest. That
is not a policy gap; it is an architecture gap. Policies say "please don't",
capabilities say "you can't".

`task-scoped-agents` closes the gap the way OAuth closed it for APIs: every
task declares exactly which tools it may call, in a grant file. The
enforcement wrapper intercepts **every** tool call at runtime. In-scope calls
execute. Out-of-scope calls are denied **before the tool body runs**, raise
`ScopeDeniedError`, and append an auditable denial event — task id, tool name,
UTC timestamp, reason — to a JSONL log. The agent physically cannot call a
tool outside its current task's declared scope, because it never holds a
reference to anything else.

## Install

Requires Python 3.10+. Zero third-party runtime dependencies (stdlib only).

```bash
git clone https://github.com/Iceman2050/task-scoped-agents.git
cd task-scoped-agents
pip install -e .
```

Run the tests:

```bash
pip install pytest
pytest -q
```

## Usage

**1. Declare the grants** in `tasks.yaml` — each task lists exactly the tools
it may call. No wildcards, no inheritance, no "all":

```yaml
tasks:
  research:
    description: "Summarize a topic from public sources"
    tools:
      - web_search
      - read_file
      - summarize
  code-review:
    description: "Read and test local code"
    tools: [read_file, run_tests]
```

**2. Run an agent under enforcement:**

```bash
task-scoped-agents run --tasks tasks.yaml --agent mock-compliant --task-id research
task-scoped-agents run --tasks tasks.yaml --agent mock-adversarial --task-id research
```

**3. Inspect the denial audit log:**

```bash
task-scoped-agents audit
task-scoped-agents audit --audit-log /path/to/denials.jsonl
```

Each denial is one JSON line:

```json
{"task_id": "research", "tool_name": "shell_exec", "timestamp": "2026-10-16T20:50:00.123456+00:00", "reason": "out_of_scope"}
```

Denial reasons: `unknown_task` (no grant for the task id), `unknown_tool`
(tool not in the registry), `out_of_scope` (tool exists but not in the grant).

## Example output

Compliant agent — everything in scope, executes normally:

```bash
$ task-scoped-agents run --tasks tasks.yaml --agent mock-compliant --task-id research
{
  "agent": "mock-compliant",
  "task_id": "research",
  "calls": [
    {"tool": "read_file", "output": "[contents of 'task-scoped agents.md']"},
    {"tool": "summarize", "output": "[summary of 'task-scoped agents']"}
  ],
  "denials": 0
}
```

Adversarial agent — does its in-scope work, then probes `shell_exec`
(registered, but outside its grant) and `exfiltrate` (not registered). Both
are denied before executing:

```bash
$ task-scoped-agents run --tasks tasks.yaml --agent mock-adversarial --task-id research --audit-log /tmp/denials.jsonl
{
  "agent": "mock-adversarial",
  "task_id": "research",
  "allowed_calls": ["read_file -> \"[contents of 'task-scoped agents.md']\""],
  "denials": [
    {"tool": "shell_exec", "reason": "out_of_scope", "timestamp": "2026-10-16T20:50:01.654321+00:00"},
    {"tool": "exfiltrate", "reason": "unknown_tool", "timestamp": "2026-10-16T20:50:01.654789+00:00"}
  ]
}

$ task-scoped-agents audit --audit-log /tmp/denials.jsonl
{"task_id": "research", "tool_name": "shell_exec", "timestamp": "2026-10-16T20:50:01.654321+00:00", "reason": "out_of_scope"}
{"task_id": "research", "tool_name": "exfiltrate", "timestamp": "2026-10-16T20:50:01.654789+00:00", "reason": "unknown_tool"}

2 denial event(s) total.
```

## Plugging in a real framework

This package ships no framework bindings on purpose — it defines a tiny
duck-typed adapter contract instead. Any object with `register(name, fn)`,
`get(name)`, and `has(name)` works as a `ToolRegistry` (see
`src/task_scoped_agents/registry.py`; subclassing is optional).

```python
from task_scoped_agents import GrantStore, ScopedExecutor, ToolRegistry

# 1. Register your framework's tools under their canonical names.
registry = ToolRegistry()
registry.register("web_search", my_framework_tool.search)
registry.register("read_file", my_framework_tool.read)

# 2. Load the grant model.
grants = GrantStore.load("tasks.yaml")

# 3. Hand the agent ONLY the executor -- never the raw registry.
executor = ScopedExecutor(task_id="research", grants=grants,
                          registry=registry, audit_log="denials.jsonl")

# 4. Route every tool call through it:
result = executor.call_tool("web_search", query="task-scoped agents")
# executor.call_tool("shell_exec", command="whoami")  # -> ScopeDeniedError + logged
```

Reloading the scope is a fresh `GrantStore.load(path)` — the tests verify a
modified `tasks.yaml` changes what is enforced on the next load.

## Project layout

```
task-scoped-agents/
├── tasks.yaml                  # grant model example
├── src/task_scoped_agents/
│   ├── __init__.py
│   ├── grants.py               # tasks.yaml -> TaskGrant allowlists
│   ├── enforcement.py          # ScopedExecutor: intercept, allow/deny, audit
│   ├── registry.py             # ToolRegistry adapter interface
│   ├── agents.py               # mock compliant + adversarial agents
│   └── cli.py                  # `run` and `audit` commands
└── tests/
    └── test_enforcement.py
```

## Built by Ingenious AI

task-scoped-agents is built and maintained by **Ingenious AI**. Get early access to the platform suite:

- [DisclosureGuard](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20DisclosureGuard)
- [ModelMinder](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20ModelMinder)
- [TermsWatch](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20TermsWatch)
- [Vibe-Code Audit](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Vibe-Code%20Audit)
- [Rogue-Agent Defense](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Rogue-Agent%20Defense)
- [BreachHunter](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20BreachHunter)
- [ChatBreaker](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20ChatBreaker)
- [Agent Flight Recorder](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Agent%20Flight%20Recorder)
- [Agent Auth Gateway](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Agent%20Auth%20Gateway)
- [DomainGuard](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20DomainGuard)
- [ContentCraft AI](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20ContentCraft%20AI)

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Ingenious AI.


> Built by Ingenious AI with Muse — get free tokens with invite code `2HCQH1`
