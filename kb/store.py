"""File I/O and storage for kanban tickets."""

import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import Ticket, Comment

KANBAN_DIR = ".kanban"
VALID_STATUSES = ("backlog", "in-progress", "done")
VALID_TYPES = ("epic", "task", "subtask")
VALID_PRIORITIES = ("low", "medium", "high", "critical")
VALID_ASSIGNEE_TYPES = ("agent", "human", "")


# ── Locate .kanban directory ──────────────────────────────────────────


def find_kanban_root() -> Optional[Path]:
    """Walk up from cwd to find a .kanban directory."""
    current = Path.cwd()
    while True:
        if (current / KANBAN_DIR).is_dir():
            return current / KANBAN_DIR
        if current == current.parent:
            break
        current = current.parent
    return None


def get_kanban_dir() -> Path:
    root = find_kanban_root()
    if root is None:
        raise FileNotFoundError(
            "No .kanban directory found. Run 'kb init' first."
        )
    return root


# ── Project initialisation ────────────────────────────────────────────


def init_project(name: str = "My Project") -> Path:
    kanban = Path.cwd() / KANBAN_DIR
    if kanban.exists():
        raise FileExistsError(f"{KANBAN_DIR} already exists in {Path.cwd()}")

    kanban.mkdir()
    for sub in ("epics", "tasks", "subtasks", "handoffs", "snapshots"):
        (kanban / sub).mkdir()

    # config
    (kanban / "config.yaml").write_text(
        f"project_name: {name}\ndefault_author: \ndefault_author_type: human\n"
    )

    # PROJECT.md
    (kanban / "PROJECT.md").write_text(
        f"# {name}\n\n"
        "## Overview\n\n_Describe your project here._\n\n"
        "## Architecture\n\n_Key architectural decisions._\n\n"
        "## Conventions\n\n_Coding conventions and standards._\n"
    )

    return kanban


# ── Frontmatter parsing ──────────────────────────────────────────────


def parse_frontmatter(text: str) -> tuple:
    """Return (metadata_dict, body_string) from a markdown file with YAML
    frontmatter delimited by ``---``."""
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()

    metadata: Dict[str, Any] = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        colon_idx = line.find(":")
        if colon_idx == -1:
            continue

        key = line[:colon_idx].strip()
        value = line[colon_idx + 1:].strip()

        # list value
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                metadata[key] = [
                    item.strip().strip('"').strip("'")
                    for item in inner.split(",")
                    if item.strip()
                ]
            else:
                metadata[key] = []
        else:
            # strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1].replace('\\"', '"')
            metadata[key] = value

    return metadata, body


def format_frontmatter(data: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            if value:
                items = ", ".join(str(v) for v in value)
                lines.append(f"{key}: [{items}]")
            else:
                lines.append(f"{key}: []")
        else:
            sv = str(value)
            if any(c in sv for c in ":#[]{}") and sv and not sv.startswith('"'):
                sv_escaped = sv.replace('"', '\\"')
                lines.append(f'{key}: "{sv_escaped}"')
            else:
                lines.append(f"{key}: {sv}")
    lines.append("---")
    return "\n".join(lines)


# ── Body section parsing ─────────────────────────────────────────────


def parse_body_sections(body: str) -> dict:
    sections = {
        "description": "",
        "acceptance_criteria": "",
        "decisions": "",
        "comments": [],
    }
    if not body:
        return sections

    # strip leading title line
    lines = body.split("\n")
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            start = i + 1
            break

    body_after_title = "\n".join(lines[start:]).strip()

    # split by ## headers
    parts = re.split(r"^## ", body_after_title, flags=re.MULTILINE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        nl = part.find("\n")
        if nl == -1:
            header, content = part, ""
        else:
            header, content = part[:nl].strip(), part[nl:].strip()

        # strip stray --- separators from section content
        content = re.sub(r"\n---\s*$", "", content).strip()

        hl = header.lower()
        if hl == "description":
            sections["description"] = content
        elif hl == "acceptance criteria":
            sections["acceptance_criteria"] = content
        elif hl == "decisions":
            sections["decisions"] = content
        elif hl.startswith("comments"):
            sections["comments"] = _parse_comments(content)

    return sections


def _parse_comments(text: str) -> List[Comment]:
    comments: List[Comment] = []
    if not text.strip():
        return comments

    parts = re.split(r"^### comment::", text, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        nl = part.find("\n")
        if nl == -1:
            header, body = part, ""
        else:
            header, body = part[:nl].strip(), part[nl:].strip()

        pieces = header.split("::")
        if len(pieces) >= 3:
            comments.append(
                Comment(
                    author=pieces[0].strip(),
                    author_type=pieces[1].strip(),
                    timestamp=pieces[2].strip(),
                    body=body,
                )
            )
    return comments


# ── Ticket ↔ markdown ─────────────────────────────────────────────────


def ticket_to_markdown(ticket: Ticket) -> str:
    fm = {
        "id": ticket.id,
        "type": ticket.type,
        "title": ticket.title,
        "status": ticket.status,
        "assignee": ticket.assignee,
        "assignee_type": ticket.assignee_type,
        "priority": ticket.priority,
        "labels": ticket.labels,
        "depends_on": ticket.depends_on,
        "files": ticket.files,
        "parent": ticket.parent,
        "source": ticket.source,
        "created": ticket.created,
        "updated": ticket.updated,
    }

    lines = [format_frontmatter(fm), ""]
    lines.append(f"# {ticket.title}")
    lines.append("")

    lines.append("## Description")
    lines.append("")
    lines.append(ticket.description if ticket.description else "_No description._")
    lines.append("")

    lines.append("## Acceptance Criteria")
    lines.append("")
    lines.append(
        ticket.acceptance_criteria
        if ticket.acceptance_criteria
        else "_None specified._"
    )
    lines.append("")

    if ticket.type == "epic":
        lines.append("## Decisions")
        lines.append("")
        lines.append(ticket.decisions if ticket.decisions else "_No decisions yet._")
        lines.append("")

    if ticket.comments:
        lines.append(f"## Comments ({len(ticket.comments)})")
        lines.append("")
        for c in ticket.comments:
            lines.append(f"### comment::{c.author}::{c.author_type}::{c.timestamp}")
            lines.append("")
            lines.append(c.body)
            lines.append("")

    return "\n".join(lines)


def markdown_to_ticket(text: str) -> Ticket:
    metadata, body = parse_frontmatter(text)
    sections = parse_body_sections(body)

    def _list(val):
        return val if isinstance(val, list) else []

    return Ticket(
        id=metadata.get("id", ""),
        type=metadata.get("type", "task"),
        title=metadata.get("title", ""),
        status=metadata.get("status", "backlog"),
        description=sections.get("description", ""),
        assignee=metadata.get("assignee", ""),
        assignee_type=metadata.get("assignee_type", ""),
        priority=metadata.get("priority", "medium"),
        labels=_list(metadata.get("labels")),
        depends_on=_list(metadata.get("depends_on")),
        files=_list(metadata.get("files")),
        parent=metadata.get("parent", ""),
        source=metadata.get("source", ""),
        created=metadata.get("created", ""),
        updated=metadata.get("updated", ""),
        comments=sections.get("comments", []),
        acceptance_criteria=sections.get("acceptance_criteria", ""),
        decisions=sections.get("decisions", ""),
    )


# ── File operations ───────────────────────────────────────────────────


def get_type_dir(ticket_type: str) -> str:
    return {"epic": "epics", "task": "tasks", "subtask": "subtasks"}[ticket_type]


def get_ticket_path(ticket_id: str) -> Path:
    kanban = get_kanban_dir()
    if "-S-" in ticket_id:
        return kanban / "subtasks" / f"{ticket_id}.md"
    elif "-T-" in ticket_id:
        return kanban / "tasks" / f"{ticket_id}.md"
    return kanban / "epics" / f"{ticket_id}.md"


def save_ticket(ticket: Ticket) -> Path:
    kanban = get_kanban_dir()
    path = kanban / get_type_dir(ticket.type) / f"{ticket.id}.md"
    path.write_text(ticket_to_markdown(ticket))
    return path


def load_ticket(ticket_id: str) -> Ticket:
    path = get_ticket_path(ticket_id)
    if not path.exists():
        raise FileNotFoundError(f"Ticket {ticket_id} not found at {path}")
    return markdown_to_ticket(path.read_text())


def delete_ticket(ticket_id: str) -> Path:
    path = get_ticket_path(ticket_id)
    if not path.exists():
        raise FileNotFoundError(f"Ticket {ticket_id} not found at {path}")
    path.unlink()
    return path


def load_all_tickets(
    type_filter: str = None,
    status_filter: str = None,
    epic_filter: str = None,
    assignee_filter: str = None,
    assignee_type_filter: str = None,
    label_filter: str = None,
) -> List[Ticket]:
    kanban = get_kanban_dir()
    tickets: List[Ticket] = []

    dirs = [get_type_dir(type_filter)] if type_filter else ["epics", "tasks", "subtasks"]

    for d in dirs:
        dir_path = kanban / d
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("*.md")):
            ticket = markdown_to_ticket(f.read_text())

            if status_filter and ticket.status != status_filter:
                continue
            if epic_filter:
                if ticket.id != epic_filter and not ticket.id.startswith(epic_filter + "-"):
                    continue
            if assignee_filter and ticket.assignee != assignee_filter:
                continue
            if assignee_type_filter and ticket.assignee_type != assignee_type_filter:
                continue
            if label_filter and label_filter not in ticket.labels:
                continue

            tickets.append(ticket)

    return tickets


# ── ID generation ─────────────────────────────────────────────────────


def _next_seq(directory: Path, prefix: str, separator: str) -> int:
    """Return the next sequence number for files matching prefix+separator+NNN."""
    pattern = f"{prefix}{separator}*.md"
    existing = sorted(directory.glob(pattern))
    if not existing:
        return 1
    last_stem = existing[-1].stem
    # extract the last numeric segment
    idx = last_stem.rfind(separator)
    if idx == -1:
        return 1
    tail = last_stem[idx + len(separator):]
    # take only the leading digits portion (before any further separator)
    match = re.match(r"(\d+)", tail)
    if match:
        return int(match.group(1)) + 1
    return 1


def next_epic_id() -> str:
    kanban = get_kanban_dir()
    seq = _next_seq(kanban / "epics", "E", "-")
    return f"E-{seq:03d}"


def next_task_id(epic_id: str) -> str:
    kanban = get_kanban_dir()
    seq = _next_seq(kanban / "tasks", epic_id + "-T", "-")
    return f"{epic_id}-T-{seq:03d}"


def next_subtask_id(task_id: str) -> str:
    kanban = get_kanban_dir()
    seq = _next_seq(kanban / "subtasks", task_id + "-S", "-")
    return f"{task_id}-S-{seq:03d}"


# ── Config helpers ────────────────────────────────────────────────────


def load_config() -> dict:
    kanban = get_kanban_dir()
    path = kanban / "config.yaml"
    if not path.exists():
        return {}
    config: Dict[str, str] = {}
    for line in path.read_text().strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            config[key.strip()] = value.strip()
    return config


def save_config(config: dict):
    kanban = get_kanban_dir()
    lines = [f"{k}: {v}" for k, v in config.items()]
    (kanban / "config.yaml").write_text("\n".join(lines) + "\n")


# ── PROJECT.md ────────────────────────────────────────────────────────


def load_project_summary() -> str:
    kanban = get_kanban_dir()
    path = kanban / "PROJECT.md"
    return path.read_text() if path.exists() else ""


def save_project_summary(text: str):
    kanban = get_kanban_dir()
    (kanban / "PROJECT.md").write_text(text)


# ── Handoffs ──────────────────────────────────────────────────────────


def save_handoff(ticket_id: str, text: str) -> Path:
    kanban = get_kanban_dir()
    path = kanban / "handoffs" / f"{ticket_id}.handoff.md"
    path.write_text(text)
    return path


def load_handoff(ticket_id: str) -> Optional[str]:
    kanban = get_kanban_dir()
    path = kanban / "handoffs" / f"{ticket_id}.handoff.md"
    return path.read_text() if path.exists() else None


# ── Snapshots ─────────────────────────────────────────────────────────


def save_snapshot(text: str) -> Path:
    kanban = get_kanban_dir()
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = kanban / "snapshots" / f"{ts}.md"
    path.write_text(text)
    return path
