"""
task-scoped-agents: per-task capability tokens for AI agents.

Public package surface. See README.md for the full story.
"""

from .enforcement import ScopedExecutor, ScopeDeniedError, DenialEvent
from .grants import GrantStore, TaskGrant
from .registry import ToolRegistry

__all__ = [
    "ScopedExecutor",
    "ScopeDeniedError",
    "DenialEvent",
    "GrantStore",
    "TaskGrant",
    "ToolRegistry",
]

__version__ = "0.1.0"
