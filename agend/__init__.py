"""
AGEND - AI Agent Iterative Manager

A supervisor/worker agent pattern for iterative task completion.
"""

__version__ = "0.2.1"

from agend.agent_cli import AgentCLI, CursorCLI, AgentType
from agend.supervisor import SupervisorAgent
from agend.worker import WorkerAgent
from agend.task_runner import TaskRunner

__all__ = [
    "AgentCLI",
    "CursorCLI",
    "AgentType",
    "SupervisorAgent",
    "WorkerAgent",
    "TaskRunner",
]
