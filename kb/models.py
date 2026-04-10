"""Data models for kanban tickets."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Comment:
    author: str
    author_type: str  # "agent" or "human"
    timestamp: str  # ISO format
    body: str


@dataclass
class Ticket:
    id: str
    type: str  # "epic", "task", "subtask"
    title: str
    status: str = "backlog"  # "backlog", "in-progress", "done"
    description: str = ""
    assignee: str = ""
    assignee_type: str = ""  # "agent", "human", ""
    priority: str = "medium"  # "low", "medium", "high", "critical"
    labels: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    parent: str = ""
    source: str = ""
    created: str = ""
    updated: str = ""
    comments: List[Comment] = field(default_factory=list)
    acceptance_criteria: str = ""
    decisions: str = ""  # decision log, primarily for epics
