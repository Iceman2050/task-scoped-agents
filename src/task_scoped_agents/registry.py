"""
Tool-registry adapter interface.

This package does not ship framework bindings; instead it defines a tiny
duck-typed contract any framework can satisfy. To plug in a real framework
(LangChain, LlamaIndex, AutoGen, a custom ReAct loop, ...):

1. Build a ``ToolRegistry`` and register each tool implementation under its
   canonical name (the same names used in ``tasks.yaml``).
2. Give the agent a ``ScopedExecutor`` (task_id + GrantStore + registry)
   and make it call ``executor.call_tool(name, **kwargs)`` for every tool
   invocation -- never the raw registry, never the raw function.

The ``ScopedExecutor`` only needs these three methods on the registry object,
so an adapter class that forwards to a framework's native tool store works
too -- no inheritance required::

    class LangChainAdapter:
        def __init__(self, tools):
            self._by_name = {t.name: t for t in tools}

        def register(self, name, fn): ...
        def get(self, name): ...
        def has(self, name): ...
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List


class ToolRegistry:
    """
    Minimal tool registry. Frameworks may subclass it or provide any object
    with the same three methods (``register`` / ``get`` / ``has``).
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a tool implementation under its canonical name."""
        if not name or not callable(fn):
            raise ValueError("register() needs a non-empty name and a callable")
        self._tools[name] = fn

    def get(self, name: str) -> Callable[..., Any]:
        """Return the implementation for *name* (KeyError if unknown)."""
        return self._tools[name]

    def has(self, name: str) -> bool:
        """True when *name* is a known tool."""
        return name in self._tools

    def tool_names(self) -> List[str]:
        return sorted(self._tools)
