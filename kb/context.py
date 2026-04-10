"""Context generation for agent briefings, handoffs, and snapshots."""

from datetime import datetime
from typing import List

from .models import Ticket
from . import store


# ── Agent context briefing ────────────────────────────────────────────


def generate_context(ticket_id: str) -> str:
    ticket = store.load_ticket(ticket_id)
    lines: List[str] = []

    lines.append(f"# Agent Context Briefing: {ticket.id}")
    lines.append("")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    lines.append("")

    # -- project summary
    project = store.load_project_summary()
    if project:
        lines.append("## Project Summary")
        lines.append("")
        lines.append(project.strip())
        lines.append("")

    # -- epic context
    epic_id = _find_epic_id(ticket)
    if epic_id and epic_id != ticket.id:
        try:
            epic = store.load_ticket(epic_id)
            lines.append(f"## Epic: {epic.id} - {epic.title}")
            lines.append(
                f"**Status:** {epic.status} | **Priority:** {epic.priority}"
            )
            lines.append("")
            if epic.description and epic.description != "_No description._":
                lines.append(epic.description)
                lines.append("")
            if epic.decisions and epic.decisions != "_No decisions yet._":
                lines.append("### Key Decisions")
                lines.append("")
                lines.append(epic.decisions)
                lines.append("")
        except FileNotFoundError:
            pass

    # -- this ticket
    kind = "Epic" if ticket.type == "epic" else "Task"
    lines.append(f"## Your {kind}: {ticket.id} - {ticket.title}")

    meta = [f"**Status:** {ticket.status}", f"**Priority:** {ticket.priority}"]
    if ticket.assignee:
        meta.append(
            f"**Assignee:** {ticket.assignee} ({ticket.assignee_type})"
        )
    if ticket.depends_on:
        dep_strs = []
        for dep_id in ticket.depends_on:
            try:
                dep = store.load_ticket(dep_id)
                dep_strs.append(f"{dep_id} ({dep.status})")
            except FileNotFoundError:
                dep_strs.append(f"{dep_id} (unknown)")
        meta.append(f"**Depends on:** {', '.join(dep_strs)}")
    lines.append(" | ".join(meta))
    lines.append("")

    if ticket.description and ticket.description != "_No description._":
        lines.append("### Description")
        lines.append("")
        lines.append(ticket.description)
        lines.append("")

    if (
        ticket.acceptance_criteria
        and ticket.acceptance_criteria != "_None specified._"
    ):
        lines.append("### Acceptance Criteria")
        lines.append("")
        lines.append(ticket.acceptance_criteria)
        lines.append("")

    if ticket.comments:
        lines.append("### Comments")
        lines.append("")
        for c in ticket.comments:
            lines.append(f"**[{c.author_type}] {c.author}** - {c.timestamp}")
            for bline in c.body.split("\n"):
                lines.append(f"> {bline}")
            lines.append("")

    if ticket.files:
        lines.append("### Relevant Files")
        lines.append("")
        for f in ticket.files:
            lines.append(f"- `{f}`")
        lines.append("")

    # -- dependency handoffs
    if ticket.depends_on:
        any_handoff = False
        for dep_id in ticket.depends_on:
            handoff = store.load_handoff(dep_id)
            if handoff:
                if not any_handoff:
                    lines.append("## Dependency Handoffs")
                    lines.append("")
                    any_handoff = True
                try:
                    dep = store.load_ticket(dep_id)
                    lines.append(f"### {dep_id}: {dep.title} ({dep.status})")
                except FileNotFoundError:
                    lines.append(f"### {dep_id}")
                lines.append("")
                lines.append(handoff.strip())
                lines.append("")

    # -- sibling tasks
    if ticket.type in ("task", "subtask") and ticket.parent:
        all_tickets = store.load_all_tickets()
        siblings = [
            t
            for t in all_tickets
            if t.parent == ticket.parent and t.id != ticket.id
        ]
        if siblings:
            lines.append("## Sibling Tasks")
            lines.append("")
            lines.append("| ID | Title | Status | Assignee |")
            lines.append("|----|-------|--------|----------|")
            for s in siblings:
                assignee = (
                    f"{s.assignee} ({s.assignee_type})"
                    if s.assignee
                    else "unassigned"
                )
                lines.append(
                    f"| {s.id} | {s.title} | {s.status} | {assignee} |"
                )
            lines.append("")

    return "\n".join(lines)


# ── Handoff ───────────────────────────────────────────────────────────


def generate_handoff_doc(ticket_id: str, message: str) -> str:
    ticket = store.load_ticket(ticket_id)

    lines: List[str] = []
    lines.append(f"# Handoff: {ticket.id} - {ticket.title}")
    lines.append("")
    lines.append(
        f"_Completed: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(message)
    lines.append("")

    if ticket.files:
        lines.append("## Files Changed")
        lines.append("")
        for f in ticket.files:
            lines.append(f"- `{f}`")
        lines.append("")

    text = "\n".join(lines)
    store.save_handoff(ticket_id, text)
    return text


# ── Snapshot ──────────────────────────────────────────────────────────


def generate_snapshot() -> str:
    config = store.load_config()
    project_name = config.get("project_name", "Project")
    all_tickets = store.load_all_tickets()

    by_status = {"backlog": 0, "in-progress": 0, "done": 0}
    by_type = {"epic": 0, "task": 0, "subtask": 0}
    for t in all_tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_type[t.type] = by_type.get(t.type, 0) + 1

    total = len(all_tickets)
    done_pct = (by_status["done"] / total * 100) if total else 0

    lines: List[str] = []
    lines.append(f"# Project Snapshot: {project_name}")
    lines.append(
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
    )
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Total tickets:** {total}")
    lines.append(
        f"- **Progress:** {by_status['done']}/{total} done ({done_pct:.0f}%)"
    )
    lines.append(
        f"- **Backlog:** {by_status['backlog']} | "
        f"**In Progress:** {by_status['in-progress']} | "
        f"**Done:** {by_status['done']}"
    )
    lines.append(
        f"- **Epics:** {by_type['epic']} | "
        f"**Tasks:** {by_type['task']} | "
        f"**Subtasks:** {by_type['subtask']}"
    )
    lines.append("")

    # per-epic breakdown
    epics = [t for t in all_tickets if t.type == "epic"]
    if epics:
        lines.append("## Epics")
        lines.append("")
        for epic in epics:
            epic_children = [
                t for t in all_tickets if t.parent == epic.id
            ]
            done_count = sum(1 for t in epic_children if t.status == "done")
            total_count = len(epic_children)
            pct = (done_count / total_count * 100) if total_count else 0

            lines.append(f"### {epic.id}: {epic.title} [{epic.status}]")
            lines.append(
                f"Progress: {done_count}/{total_count} tasks ({pct:.0f}%)"
            )
            lines.append("")

            marker_map = {
                "backlog": "[ ]",
                "in-progress": "[~]",
                "done": "[x]",
            }
            for task in epic_children:
                assignee = (
                    f"{task.assignee} ({task.assignee_type})"
                    if task.assignee
                    else "unassigned"
                )
                marker = marker_map.get(task.status, "[ ]")
                lines.append(
                    f"- {marker} {task.id}: {task.title} | {assignee}"
                )
            lines.append("")

    # unassigned work
    unassigned = [
        t for t in all_tickets if not t.assignee and t.status != "done"
    ]
    if unassigned:
        lines.append("## Unassigned Work")
        lines.append("")
        for t in unassigned:
            lines.append(f"- {t.id}: {t.title} [{t.priority}]")
        lines.append("")

    # blocked tickets
    done_ids = {t.id for t in all_tickets if t.status == "done"}
    blocked = []
    for t in all_tickets:
        if t.depends_on and t.status != "done":
            unmet = [d for d in t.depends_on if d not in done_ids]
            if unmet:
                blocked.append((t, unmet))
    if blocked:
        lines.append("## Blocked")
        lines.append("")
        for t, deps in blocked:
            lines.append(
                f"- {t.id}: {t.title} -- waiting on {', '.join(deps)}"
            )
        lines.append("")

    return "\n".join(lines)


# ── helpers ───────────────────────────────────────────────────────────


def _find_epic_id(ticket: Ticket) -> str:
    if ticket.type == "epic":
        return ticket.id
    if ticket.type == "task":
        return ticket.parent
    if ticket.type == "subtask" and ticket.parent:
        try:
            parent_task = store.load_ticket(ticket.parent)
            return parent_task.parent
        except FileNotFoundError:
            pass
    return ""
