"""CLI entry point for the kb command."""

import sys
import os
import json
import argparse
from datetime import datetime

from . import store
from .models import Ticket, Comment
from .board import render_board
from .context import generate_context, generate_handoff_doc, generate_snapshot


# ── Commands ──────────────────────────────────────────────────────────


def cmd_init(args):
    name = args.name
    slug = args.id or None
    try:
        path = store.init_project(name, slug)
        actual_slug = path.name
        print(f"Created project '{name}' ({actual_slug})")
        print(f"  Location: {path}")
        print(f"  Active project set to: {actual_slug}")
        print()
        print("Next steps:")
        print(f"  kb create epic \"Epic title\"")
    except FileExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_projects(args):
    projects = store.list_projects()
    active = store.get_active_project()

    if not projects:
        print("No projects. Run 'kb init <name>' to create one.")
        return

    print(f"{'  '} {'Slug':<24} Name")
    print("-" * 60)
    for p in projects:
        marker = "->" if p["slug"] == active else "  "
        print(f"{marker} {p['slug']:<24} {p['name']}")
    print(f"\n{len(projects)} project(s)")


def cmd_use(args):
    slug = args.project
    # verify it exists
    home = store.get_kanban_home()
    if not (home / "projects" / slug).exists():
        # try fuzzy match
        projects = store.list_projects()
        matches = [p for p in projects if slug in p["slug"] or slug in p["name"].lower()]
        if len(matches) == 1:
            slug = matches[0]["slug"]
        else:
            print(f"Error: Project '{slug}' not found.", file=sys.stderr)
            if matches:
                print("Did you mean:", file=sys.stderr)
                for m in matches:
                    print(f"  {m['slug']} ({m['name']})", file=sys.stderr)
            else:
                print("Run 'kb projects' to see available projects.", file=sys.stderr)
            sys.exit(1)

    store.set_active_project(slug)
    cfg = store.load_config()
    name = cfg.get("project_name", slug)
    print(f"Switched to project: {name} ({slug})")


def cmd_create(args):
    now = datetime.now().isoformat(timespec="seconds")
    ticket_type = args.type
    title = args.title

    try:
        if ticket_type == "epic":
            ticket_id = store.next_epic_id()
            parent = ""
        elif ticket_type == "task":
            if not args.epic:
                print(
                    "Error: --epic is required when creating a task",
                    file=sys.stderr,
                )
                sys.exit(1)
            store.load_ticket(args.epic)
            ticket_id = store.next_task_id(args.epic)
            parent = args.epic
        elif ticket_type == "subtask":
            if not args.task:
                print(
                    "Error: --task is required when creating a subtask",
                    file=sys.stderr,
                )
                sys.exit(1)
            store.load_ticket(args.task)
            ticket_id = store.next_subtask_id(args.task)
            parent = args.task
        else:
            print(f"Error: Unknown type: {ticket_type}", file=sys.stderr)
            sys.exit(1)

        labels = (
            [l.strip() for l in args.labels.split(",") if l.strip()]
            if args.labels
            else []
        )
        depends_on = (
            [d.strip() for d in args.depends_on.split(",") if d.strip()]
            if args.depends_on
            else []
        )

        description = args.description or ""
        if args.description_file:
            with open(args.description_file) as f:
                description = f.read()

        ticket = Ticket(
            id=ticket_id,
            type=ticket_type,
            title=title,
            status="backlog",
            description=description,
            assignee=args.assignee or "",
            assignee_type=args.assignee_type or "",
            priority=args.priority or "medium",
            labels=labels,
            depends_on=depends_on,
            parent=parent,
            source=args.source or "",
            created=now,
            updated=now,
            acceptance_criteria=args.acceptance_criteria or "",
        )

        path = store.save_ticket(ticket)
        print(f"Created {ticket_type} {ticket_id}: {title}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_board(args):
    try:
        tickets = store.load_all_tickets(
            type_filter=args.type,
            epic_filter=args.epic,
            assignee_type_filter=args.assignee_type,
        )
        config = store.load_config()
        title = config.get("project_name", "")
        if args.epic:
            title += f" | Epic: {args.epic}"
        print(render_board(tickets, title))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    try:
        tickets = store.load_all_tickets(
            type_filter=args.type,
            status_filter=args.status,
            epic_filter=args.epic,
            assignee_filter=args.assignee,
            assignee_type_filter=args.assignee_type,
            label_filter=args.label,
        )

        if not tickets:
            print("No tickets found.")
            return

        print(
            f"{'ID':<22} {'Type':<8} {'Status':<13} {'Pri':<9} "
            f"{'Assignee':<20} Title"
        )
        print("-" * 105)

        for t in tickets:
            assignee = ""
            if t.assignee:
                assignee = (
                    f"{t.assignee} ({t.assignee_type})"
                    if t.assignee_type
                    else t.assignee
                )
            title = t.title
            if len(title) > 38:
                title = title[:35] + "..."
            print(
                f"{t.id:<22} {t.type:<8} {t.status:<13} {t.priority:<9} "
                f"{assignee:<20} {title}"
            )

        print(f"\n{len(tickets)} ticket(s)")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_show(args):
    try:
        ticket = store.load_ticket(args.id)
        width = 62

        print("=" * width)
        print(f" {ticket.id}: {ticket.title}")
        print("=" * width)

        assignee = "unassigned"
        if ticket.assignee:
            assignee = (
                f"{ticket.assignee} ({ticket.assignee_type})"
                if ticket.assignee_type
                else ticket.assignee
            )

        print(f" Type:     {ticket.type:<16} Status:   {ticket.status}")
        print(f" Priority: {ticket.priority:<16} Assignee: {assignee}")
        if ticket.parent:
            print(f" Parent:   {ticket.parent}")
        if ticket.labels:
            print(f" Labels:   {', '.join(ticket.labels)}")
        if ticket.depends_on:
            print(f" Depends:  {', '.join(ticket.depends_on)}")
        if ticket.files:
            print(f" Files:    {', '.join(ticket.files)}")
        if ticket.source:
            print(f" Source:   {ticket.source}")
        print(f" Created:  {ticket.created}")
        print(f" Updated:  {ticket.updated}")

        print("-" * width)

        if ticket.description and ticket.description != "_No description._":
            print("\n## Description\n")
            print(ticket.description)

        if (
            ticket.acceptance_criteria
            and ticket.acceptance_criteria != "_None specified._"
        ):
            print("\n## Acceptance Criteria\n")
            print(ticket.acceptance_criteria)

        if (
            ticket.type == "epic"
            and ticket.decisions
            and ticket.decisions != "_No decisions yet._"
        ):
            print("\n## Decisions\n")
            print(ticket.decisions)

        if ticket.comments:
            print("\n" + "-" * width)
            print(f"\n## Comments ({len(ticket.comments)})\n")
            for c in ticket.comments:
                print(f"[{c.author_type}] {c.author} - {c.timestamp}")
                for line in c.body.split("\n"):
                    print(f"  {line}")
                print()

        print("=" * width)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_edit(args):
    try:
        ticket = store.load_ticket(args.id)
        updated = False

        if args.title is not None:
            ticket.title = args.title
            updated = True
        if args.description is not None:
            ticket.description = args.description
            updated = True
        if args.description_file:
            with open(args.description_file) as f:
                ticket.description = f.read()
            updated = True
        if args.status:
            if args.status not in store.VALID_STATUSES:
                print(
                    f"Error: Invalid status. Choose from: "
                    f"{', '.join(store.VALID_STATUSES)}",
                    file=sys.stderr,
                )
                sys.exit(1)
            ticket.status = args.status
            updated = True
        if args.priority:
            if args.priority not in store.VALID_PRIORITIES:
                print(
                    f"Error: Invalid priority. Choose from: "
                    f"{', '.join(store.VALID_PRIORITIES)}",
                    file=sys.stderr,
                )
                sys.exit(1)
            ticket.priority = args.priority
            updated = True
        if args.add_label:
            for label in args.add_label.split(","):
                label = label.strip()
                if label and label not in ticket.labels:
                    ticket.labels.append(label)
            updated = True
        if args.remove_label:
            for label in args.remove_label.split(","):
                label = label.strip()
                if label in ticket.labels:
                    ticket.labels.remove(label)
            updated = True
        if args.acceptance_criteria is not None:
            ticket.acceptance_criteria = args.acceptance_criteria
            updated = True
        if args.add_depends:
            for dep in args.add_depends.split(","):
                dep = dep.strip()
                if dep and dep not in ticket.depends_on:
                    ticket.depends_on.append(dep)
            updated = True
        if args.remove_depends:
            for dep in args.remove_depends.split(","):
                dep = dep.strip()
                if dep in ticket.depends_on:
                    ticket.depends_on.remove(dep)
            updated = True
        if args.add_file:
            for fp in args.add_file.split(","):
                fp = fp.strip()
                if fp and fp not in ticket.files:
                    ticket.files.append(fp)
            updated = True
        if args.remove_file:
            for fp in args.remove_file.split(","):
                fp = fp.strip()
                if fp in ticket.files:
                    ticket.files.remove(fp)
            updated = True
        if args.source is not None:
            ticket.source = args.source
            updated = True
        if args.decisions is not None:
            ticket.decisions = args.decisions
            updated = True

        if not updated:
            editor = os.environ.get(
                "EDITOR", os.environ.get("VISUAL", "vi")
            )
            path = store.get_ticket_path(args.id)
            os.system(f'{editor} "{path}"')
            print(f"Opened {args.id} in editor.")
            return

        ticket.updated = datetime.now().isoformat(timespec="seconds")
        store.save_ticket(ticket)
        print(f"Updated {args.id}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_move(args):
    try:
        status = args.status
        if status not in store.VALID_STATUSES:
            print(
                f"Error: Invalid status. Choose from: "
                f"{', '.join(store.VALID_STATUSES)}",
                file=sys.stderr,
            )
            sys.exit(1)

        ticket = store.load_ticket(args.id)
        old = ticket.status
        ticket.status = status
        ticket.updated = datetime.now().isoformat(timespec="seconds")
        store.save_ticket(ticket)
        print(f"Moved {args.id}: {old} -> {status}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_comment(args):
    try:
        ticket = store.load_ticket(args.id)

        config = store.load_config()
        author = args.author or config.get("default_author", "") or "anonymous"
        author_type = args.author_type or config.get(
            "default_author_type", "human"
        )

        if author_type not in ("agent", "human"):
            print(
                "Error: --author-type must be 'agent' or 'human'",
                file=sys.stderr,
            )
            sys.exit(1)

        comment = Comment(
            author=author,
            author_type=author_type,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            body=args.message,
        )
        ticket.comments.append(comment)
        ticket.updated = datetime.now().isoformat(timespec="seconds")
        store.save_ticket(ticket)
        print(f"Comment added to {args.id} by {author} ({author_type})")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_assign(args):
    try:
        ticket = store.load_ticket(args.id)
        ticket.assignee = args.assignee
        ticket.assignee_type = args.type or "human"
        ticket.updated = datetime.now().isoformat(timespec="seconds")
        store.save_ticket(ticket)
        print(
            f"Assigned {args.id} to {args.assignee} ({ticket.assignee_type})"
        )

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_unassign(args):
    try:
        ticket = store.load_ticket(args.id)
        old = ticket.assignee or "nobody"
        ticket.assignee = ""
        ticket.assignee_type = ""
        ticket.updated = datetime.now().isoformat(timespec="seconds")
        store.save_ticket(ticket)
        print(f"Unassigned {args.id} (was: {old})")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_context(args):
    try:
        ctx = generate_context(args.id)
        if args.output:
            with open(args.output, "w") as f:
                f.write(ctx)
            print(f"Context written to {args.output}")
        else:
            print(ctx)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_handoff(args):
    try:
        if args.message:
            message = args.message
        elif args.message_file:
            with open(args.message_file) as f:
                message = f.read()
        else:
            print("Enter handoff notes (Ctrl+D to finish):")
            message = sys.stdin.read()

        doc = generate_handoff_doc(args.id, message)
        print(f"Handoff saved for {args.id}")
        if args.verbose:
            print()
            print(doc)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_snapshot(args):
    try:
        text = generate_snapshot()
        path = store.save_snapshot(text)
        print(text)
        print(f"\nSnapshot saved to {path}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args):
    try:
        ticket = store.load_ticket(args.id)
        if not args.force:
            answer = input(f"Delete {args.id}: {ticket.title}? [y/N] ")
            if answer.lower() != "y":
                print("Cancelled.")
                return
        store.delete_ticket(args.id)
        print(f"Deleted {args.id}: {ticket.title}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_import(args):
    try:
        if args.file:
            with open(args.file) as f:
                data = json.load(f)
        elif args.json_str:
            data = json.loads(args.json_str)
        else:
            print("Reading JSON from stdin...")
            data = json.load(sys.stdin)

        now = datetime.now().isoformat(timespec="seconds")
        imported = []

        def _import_epic(ed):
            eid = store.next_epic_id()
            epic = Ticket(
                id=eid,
                type="epic",
                title=ed.get("title", "Untitled Epic"),
                description=ed.get("description", ""),
                priority=ed.get("priority", "medium"),
                labels=ed.get("labels", []),
                source=ed.get("source", ""),
                acceptance_criteria=ed.get("acceptance_criteria", ""),
                decisions=ed.get("decisions", ""),
                created=now,
                updated=now,
            )
            store.save_ticket(epic)
            imported.append(epic)
            for td in ed.get("tasks", []):
                _import_task(td, eid)

        def _import_task(td, epic_id):
            tid = store.next_task_id(epic_id)
            task = Ticket(
                id=tid,
                type="task",
                title=td.get("title", "Untitled Task"),
                description=td.get("description", ""),
                priority=td.get("priority", "medium"),
                labels=td.get("labels", []),
                depends_on=td.get("depends_on", []),
                parent=epic_id,
                source=td.get("source", ""),
                acceptance_criteria=td.get("acceptance_criteria", ""),
                created=now,
                updated=now,
            )
            store.save_ticket(task)
            imported.append(task)
            for sd in td.get("subtasks", []):
                _import_subtask(sd, tid)

        def _import_subtask(sd, task_id):
            sid = store.next_subtask_id(task_id)
            sub = Ticket(
                id=sid,
                type="subtask",
                title=sd.get("title", "Untitled Subtask"),
                description=sd.get("description", ""),
                priority=sd.get("priority", "medium"),
                labels=sd.get("labels", []),
                parent=task_id,
                source=sd.get("source", ""),
                acceptance_criteria=sd.get("acceptance_criteria", ""),
                created=now,
                updated=now,
            )
            store.save_ticket(sub)
            imported.append(sub)

        items = data if isinstance(data, list) else [data]
        for item in items:
            t = item.get("type", "epic")
            if t == "epic":
                _import_epic(item)
            elif t == "task" and "epic" in item:
                _import_task(item, item["epic"])
            elif t == "subtask" and "task" in item:
                _import_subtask(item, item["task"])
            else:
                _import_epic(item)

        print(f"Imported {len(imported)} ticket(s):")
        for t in imported:
            print(f"  {t.id}: {t.title}")

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ── Argument parser ───────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kb",
        description="Global project management for AI agents and humans",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )
    parser.add_argument(
        "--project", "-P",
        help="Override active project (use project slug)",
        metavar="SLUG",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── init
    p = sub.add_parser("init", help="Create a new project")
    p.add_argument("name", help="Project name")
    p.add_argument("--id", help="Custom slug (default: derived from name)")
    p.set_defaults(func=cmd_init)

    # ── projects
    p = sub.add_parser("projects", help="List all projects")
    p.set_defaults(func=cmd_projects)

    # ── use
    p = sub.add_parser("use", help="Switch active project")
    p.add_argument("project", help="Project slug")
    p.set_defaults(func=cmd_use)

    # ── create
    p = sub.add_parser("create", help="Create a new ticket")
    p.add_argument("type", choices=["epic", "task", "subtask"])
    p.add_argument("title")
    p.add_argument("--epic", "-e", help="Parent epic ID (for tasks)")
    p.add_argument("--task", "-t", help="Parent task ID (for subtasks)")
    p.add_argument("--description", "-d", help="Description text")
    p.add_argument("--description-file", help="Read description from file")
    p.add_argument(
        "--priority",
        "-p",
        choices=["low", "medium", "high", "critical"],
        default="medium",
    )
    p.add_argument("--labels", "-l", help="Comma-separated labels")
    p.add_argument("--depends-on", help="Comma-separated dependency IDs")
    p.add_argument("--assignee", help="Assignee name")
    p.add_argument(
        "--assignee-type", choices=["agent", "human"], help="Assignee type"
    )
    p.add_argument("--acceptance-criteria", help="Acceptance criteria")
    p.add_argument("--source", "-s", help="Source reference (e.g. JIRA:PROJ-123)")
    p.set_defaults(func=cmd_create)

    # ── board
    p = sub.add_parser("board", help="Display ASCII kanban board")
    p.add_argument("--epic", "-e", help="Filter by epic")
    p.add_argument("--type", choices=["epic", "task", "subtask"])
    p.add_argument(
        "--assignee-type", choices=["agent", "human"], help="Filter by type"
    )
    p.set_defaults(func=cmd_board)

    # ── list
    p = sub.add_parser("list", help="List tickets with filters")
    p.add_argument("--type", choices=["epic", "task", "subtask"])
    p.add_argument("--status", choices=["backlog", "in-progress", "done"])
    p.add_argument("--epic", "-e", help="Filter by epic")
    p.add_argument("--assignee", help="Filter by assignee name")
    p.add_argument("--assignee-type", choices=["agent", "human"])
    p.add_argument("--label", help="Filter by label")
    p.set_defaults(func=cmd_list)

    # ── show
    p = sub.add_parser("show", help="Show ticket details")
    p.add_argument("id", help="Ticket ID (e.g. E-001, E-001-T-003)")
    p.set_defaults(func=cmd_show)

    # ── edit
    p = sub.add_parser(
        "edit", help="Edit a ticket (no flags opens in $EDITOR)"
    )
    p.add_argument("id")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--description-file")
    p.add_argument("--status", choices=["backlog", "in-progress", "done"])
    p.add_argument(
        "--priority", choices=["low", "medium", "high", "critical"]
    )
    p.add_argument("--add-label", help="Add labels (comma-separated)")
    p.add_argument("--remove-label", help="Remove labels (comma-separated)")
    p.add_argument("--acceptance-criteria")
    p.add_argument("--add-depends", help="Add dependency IDs")
    p.add_argument("--remove-depends", help="Remove dependency IDs")
    p.add_argument("--add-file", help="Add file paths")
    p.add_argument("--remove-file", help="Remove file paths")
    p.add_argument("--source")
    p.add_argument("--decisions", help="Set decisions (epics)")
    p.set_defaults(func=cmd_edit)

    # ── move
    p = sub.add_parser("move", help="Change ticket status")
    p.add_argument("id")
    p.add_argument("status", choices=["backlog", "in-progress", "done"])
    p.set_defaults(func=cmd_move)

    # ── comment
    p = sub.add_parser("comment", help="Add a comment to a ticket")
    p.add_argument("id")
    p.add_argument("message")
    p.add_argument("--author", "-a", help="Author name")
    p.add_argument(
        "--author-type", choices=["agent", "human"], help="Author type"
    )
    p.set_defaults(func=cmd_comment)

    # ── assign
    p = sub.add_parser("assign", help="Assign a ticket")
    p.add_argument("id")
    p.add_argument("assignee", help="Assignee name")
    p.add_argument(
        "--type",
        choices=["agent", "human"],
        default="human",
        help="Assignee type",
    )
    p.set_defaults(func=cmd_assign)

    # ── unassign
    p = sub.add_parser("unassign", help="Remove ticket assignment")
    p.add_argument("id")
    p.set_defaults(func=cmd_unassign)

    # ── context
    p = sub.add_parser("context", help="Generate agent context briefing")
    p.add_argument("id")
    p.add_argument("--output", "-o", help="Write to file instead of stdout")
    p.set_defaults(func=cmd_context)

    # ── handoff
    p = sub.add_parser("handoff", help="Write handoff notes for completed work")
    p.add_argument("id")
    p.add_argument("--message", "-m", help="Handoff message")
    p.add_argument("--message-file", help="Read message from file")
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Print after saving"
    )
    p.set_defaults(func=cmd_handoff)

    # ── snapshot
    p = sub.add_parser("snapshot", help="Generate project-wide status snapshot")
    p.set_defaults(func=cmd_snapshot)

    # ── delete
    p = sub.add_parser("delete", help="Delete a ticket")
    p.add_argument("id")
    p.add_argument(
        "--force", "-f", action="store_true", help="Skip confirmation"
    )
    p.set_defaults(func=cmd_delete)

    # ── import
    p = sub.add_parser("import", help="Import tickets from JSON")
    p.add_argument("--file", "-f", help="JSON file path")
    p.add_argument("--json", dest="json_str", help="JSON string")
    p.set_defaults(func=cmd_import)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # apply --project override before any command runs
    if hasattr(args, "project") and args.project and args.command not in ("init", "projects", "use"):
        store.set_project_override(args.project)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
