"""Interactive TUI for kb using Textual."""

from __future__ import annotations

import sys
from datetime import datetime

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    OptionList,
    Select,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option

from . import store
from .models import Ticket, Comment
from .context import generate_context, generate_snapshot


# ── Colour helpers ────────────────────────────────────────────────────

STATUS_COLORS = {
    "backlog": "grey",
    "in-progress": "yellow",
    "done": "green",
}
NARROW_TERMINAL_WIDTH = 120

PRIORITY_COLORS = {
    "critical": "red bold",
    "high": "dark_orange",
    "medium": "yellow",
    "low": "grey",
}


def _status_badge(status: str) -> str:
    c = STATUS_COLORS.get(status, "white")
    return f"[{c}]{status}[/]"


def _priority_badge(priority: str) -> str:
    c = PRIORITY_COLORS.get(priority, "white")
    return f"[{c}]{priority}[/]"


def _assignee_badge(ticket: Ticket) -> str:
    if not ticket.assignee:
        return "[dim]unassigned[/]"
    if ticket.assignee_type == "agent":
        return f"[cyan]{ticket.assignee}[/] [dim](agent)[/]"
    return f"[magenta]{ticket.assignee}[/] [dim](human)[/]"


# ── Hierarchy helpers ─────────────────────────────────────────────────


def _build_hierarchy(tickets: list[Ticket]) -> list[dict]:
    """Organise tickets into a tree: epics → tasks → subtasks.

    Returns a list of dicts:
      {"epic": Ticket|None, "tasks": [{"task": Ticket, "subtasks": [Ticket]}]}

    Tickets with no parent epic are grouped under a synthetic ``None`` epic.
    """
    epics: dict[str, Ticket] = {}
    tasks_by_epic: dict[str, list[Ticket]] = {}
    subtasks_by_task: dict[str, list[Ticket]] = {}
    orphan_tickets: list[Ticket] = []

    for t in tickets:
        if t.type == "epic":
            epics[t.id] = t
            tasks_by_epic.setdefault(t.id, [])
        elif t.type == "task":
            if t.parent:
                tasks_by_epic.setdefault(t.parent, []).append(t)
            else:
                orphan_tickets.append(t)
        elif t.type == "subtask":
            if t.parent:
                subtasks_by_task.setdefault(t.parent, []).append(t)
            else:
                orphan_tickets.append(t)

    result = []

    # known epics with their children
    for eid in sorted(epics):
        epic = epics[eid]
        task_nodes = []
        for task in tasks_by_epic.get(eid, []):
            task_nodes.append({
                "task": task,
                "subtasks": subtasks_by_task.get(task.id, []),
            })
        result.append({"epic": epic, "tasks": task_nodes})

    # tasks whose epic isn't in the current ticket set (e.g. filtered out)
    seen_tasks = {t["task"].id for grp in result for t in grp["tasks"]}
    for eid, tlist in tasks_by_epic.items():
        if eid not in epics:
            task_nodes = []
            for task in tlist:
                if task.id not in seen_tasks:
                    task_nodes.append({
                        "task": task,
                        "subtasks": subtasks_by_task.get(task.id, []),
                    })
            if task_nodes:
                result.append({"epic": None, "tasks": task_nodes})

    # true orphans
    if orphan_tickets:
        task_nodes = [{"task": t, "subtasks": []} for t in orphan_tickets]
        result.append({"epic": None, "tasks": task_nodes})

    return result


# ── Ticket detail markdown ────────────────────────────────────────────


def _normalize_tables(text: str) -> str:
    """Turn runs of pipe-delimited lines into GFM tables so Markdown renders them as tables."""
    out: list[str] = []
    run_raw: list[str] = []
    run_cells: list[list[str]] = []

    def flush() -> None:
        if len(run_cells) >= 2:
            width = max(len(r) for r in run_cells)
            rows = [r + [""] * (width - len(r)) for r in run_cells]
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "|".join(" --- " for _ in range(width)) + "|")
            for r in rows[1:]:
                out.append("| " + " | ".join(r) + " |")
        else:
            out.extend(run_raw)
        run_raw.clear()
        run_cells.clear()

    in_fence = False
    in_existing_table = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            in_existing_table = False
            out.append(line)
            continue
        cells = _table_cells(stripped)
        if not in_fence and cells is not None:
            if in_existing_table:
                out.append(line)
            elif run_cells and _is_separator_row(cells):
                out.extend(run_raw)
                run_raw.clear()
                run_cells.clear()
                out.append(line)
                in_existing_table = True
            else:
                run_raw.append(line)
                run_cells.append(cells)
            continue
        in_existing_table = False
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


def _table_cells(line: str) -> "list[str] | None":
    if line.count("|") < 1 or line.startswith(("- ", "* ", "+ ", ">", "#")):
        return None
    if line.startswith("|") and line.endswith("|"):
        line = line[1:-1]
    elif " | " not in line:
        return None
    return [c.strip() for c in line.split("|")]


def _is_separator_row(cells: "list[str]") -> bool:
    return all(c and set(c) <= set("-: ") for c in cells)


def _ticket_detail_md(ticket: Ticket) -> str:
    lines = []
    lines.append(f"# {ticket.id}: {ticket.title}")
    lines.append("")

    assignee = "unassigned"
    if ticket.assignee:
        assignee = f"{ticket.assignee} ({ticket.assignee_type})" if ticket.assignee_type else ticket.assignee

    lines.append(f"**Type:** {ticket.type}  |  **Status:** {ticket.status}  |  **Priority:** {ticket.priority}")
    lines.append(f"**Assignee:** {assignee}")
    if ticket.parent:
        lines.append(f"**Parent:** {ticket.parent}")
    if ticket.labels:
        lines.append(f"**Labels:** {', '.join(ticket.labels)}")
    if ticket.depends_on:
        lines.append(f"**Depends on:** {', '.join(ticket.depends_on)}")
    if ticket.files:
        lines.append(f"**Files:** {', '.join(ticket.files)}")
    if ticket.source:
        lines.append(f"**Source:** {ticket.source}")
    lines.append(f"**Created:** {ticket.created}  |  **Updated:** {ticket.updated}")
    lines.append("")

    if ticket.description and ticket.description != "_No description._":
        lines.append("## Description")
        lines.append("")
        lines.append(_normalize_tables(ticket.description))
        lines.append("")

    if ticket.acceptance_criteria and ticket.acceptance_criteria != "_None specified._":
        lines.append("## Acceptance Criteria")
        lines.append("")
        lines.append(_normalize_tables(ticket.acceptance_criteria))
        lines.append("")

    if ticket.type == "epic" and ticket.decisions and ticket.decisions != "_No decisions yet._":
        lines.append("## Decisions")
        lines.append("")
        lines.append(_normalize_tables(ticket.decisions))
        lines.append("")

    if ticket.comments:
        lines.append(f"## Comments ({len(ticket.comments)})")
        lines.append("")
        for c in ticket.comments:
            lines.append(f"**[{c.author_type}] {c.author}** — {c.timestamp}")
            lines.append("")
            lines.append(_normalize_tables(c.body))
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


# ── Comment modal ─────────────────────────────────────────────────────


class CommentModal(ModalScreen[str | None]):
    """Modal for adding a comment to a ticket."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    CommentModal {
        align: center middle;
    }
    CommentModal > Vertical {
        width: 70;
        height: auto;
        max-height: 20;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    CommentModal Input {
        margin-bottom: 1;
    }
    CommentModal TextArea {
        height: 6;
        margin-bottom: 1;
    }
    """

    def __init__(self, ticket_id: str):
        super().__init__()
        self.ticket_id = ticket_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Comment on {self.ticket_id}", id="comment-title")
            yield Input(placeholder="Author name", id="comment-author")
            yield Select(
                [("human", "human"), ("agent", "agent")],
                value="human",
                id="comment-type",
            )
            yield TextArea(id="comment-body")
            yield Label("[dim]Enter to submit | Escape to cancel[/]")

    def on_mount(self) -> None:
        self.query_one("#comment-author", Input).focus()

    @on(Input.Submitted, "#comment-author")
    def focus_body(self) -> None:
        self.query_one("#comment-body", TextArea).focus()

    def key_ctrl_s(self) -> None:
        self._submit()

    def _submit(self) -> None:
        author = self.query_one("#comment-author", Input).value.strip() or "anonymous"
        author_type = self.query_one("#comment-type", Select).value
        body = self.query_one("#comment-body", TextArea).text.strip()
        if not body:
            self.dismiss(None)
            return
        try:
            ticket = store.load_ticket(self.ticket_id)
            ticket.comments.append(Comment(
                author=author,
                author_type=author_type,
                timestamp=datetime.now().isoformat(timespec="seconds"),
                body=body,
            ))
            ticket.updated = datetime.now().isoformat(timespec="seconds")
            store.save_ticket(ticket)
            self.dismiss(f"Comment added by {author}")
        except Exception as e:
            self.dismiss(f"Error: {e}")

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Move modal ────────────────────────────────────────────────────────


class MoveModal(ModalScreen[str | None]):
    """Modal for changing ticket status."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    MoveModal {
        align: center middle;
    }
    MoveModal > Vertical {
        width: 40;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, ticket_id: str, current_status: str):
        super().__init__()
        self.ticket_id = ticket_id
        self.current_status = current_status

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Move {self.ticket_id}")
            yield OptionList(
                Option("backlog", id="backlog"),
                Option("in-progress", id="in-progress"),
                Option("done", id="done"),
            )

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        new_status = event.option.id
        try:
            ticket = store.load_ticket(self.ticket_id)
            old = ticket.status
            ticket.status = new_status
            ticket.updated = datetime.now().isoformat(timespec="seconds")
            store.save_ticket(ticket)
            self.dismiss(f"Moved {self.ticket_id}: {old} -> {new_status}")
        except Exception as e:
            self.dismiss(f"Error: {e}")

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main app ──────────────────────────────────────────────────────────


class KanbanApp(App):
    """TUI for kb project management."""

    TITLE = "kb"
    SUB_TITLE = ""

    BINDINGS = [
        Binding("b", "view_board", "Board"),
        Binding("l", "view_list", "List"),
        Binding("s", "view_snapshot", "Snapshot"),
        Binding("p", "switch_project", "Projects"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    Screen {
        background: $surface;
    }

    /* ── Board view ─────────────────────────── */

    #board-container {
        height: 1fr;
    }
    .board-column {
        width: 1fr;
        border: solid $primary-background;
        height: 100%;
    }
    .board-column > Static.column-header {
        text-align: center;
        text-style: bold;
        background: $primary-background;
        color: $text;
        padding: 0 1;
        width: 100%;
    }
    .board-column OptionList {
        height: 1fr;
    }

    /* ── List view ──────────────────────────── */

    #list-container {
        height: 1fr;
    }
    #list-container DataTable {
        height: 1fr;
    }

    /* ── Detail panel ───────────────────────── */

    #detail-panel {
        width: 1fr;
        height: 1fr;
        border: solid $accent;
        display: none;
    }
    #detail-panel.visible {
        display: block;
    }
    #detail-md {
        padding: 1 2;
    }

    /* ── Snapshot view ──────────────────────── */

    #snapshot-container {
        height: 1fr;
        display: none;
        padding: 1 2;
    }
    #snapshot-container.visible {
        display: block;
    }

    /* ── Project switcher ───────────────────── */

    #project-switcher {
        display: none;
        height: 1fr;
        border: solid $accent;
    }
    #project-switcher.visible {
        display: block;
    }

    /* ── Status bar ─────────────────────────── */

    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }

    /* ── View containers ────────────────────── */

    #main-area {
        height: 1fr;
    }
    """

    def __init__(self, project_slug: str = None, initial_view: str = "board"):
        super().__init__()
        self._project_slug = project_slug
        self._current_view = initial_view
        self._selected_ticket_id: str | None = None
        self._filter_type: str | None = None
        self._filter_cycle = [None, "epic", "task", "subtask"]
        self._filter_idx = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            # board view
            with Horizontal(id="board-container"):
                for col_id, col_name in [("col-backlog", "BACKLOG"), ("col-progress", "IN PROGRESS"), ("col-done", "DONE")]:
                    with Vertical(classes="board-column", id=col_id):
                        yield Static(col_name, classes="column-header")
                        yield OptionList(id=f"opts-{col_id}")

            # list view
            with Vertical(id="list-container"):
                yield DataTable(id="ticket-table")

            # snapshot view
            with VerticalScroll(id="snapshot-container"):
                yield Markdown(id="snapshot-md")

            # project switcher
            with Vertical(id="project-switcher"):
                yield Label("Switch Project", id="proj-label")
                yield OptionList(id="project-list")

            # detail panel
            with VerticalScroll(id="detail-panel"):
                yield Markdown(id="detail-md")

        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        if self._project_slug:
            store.set_project_override(self._project_slug)

        try:
            slug = store.get_active_project()
            config = store.load_config()
            name = config.get("project_name", slug)
            self.sub_title = f"{name} ({slug})"
        except FileNotFoundError:
            self.sub_title = "No active project"

        # setup table columns
        table = self.query_one("#ticket-table", DataTable)
        table.add_columns("ID", "Type", "Status", "Priority", "Assignee", "Title")
        table.cursor_type = "row"

        # hide list and snapshot by default
        self.query_one("#list-container").display = False
        self.query_one("#snapshot-container").display = False
        self.query_one("#project-switcher").display = False

        self._open_initial_view()

    def _open_initial_view(self) -> None:
        if self._current_view == "list":
            self.action_view_list()
        elif self._current_view == "snapshot":
            self.action_view_snapshot()
        else:
            self.action_view_board()

    # ── Data loading ──────────────────────────────────────────────────

    def _load_tickets(self) -> list[Ticket]:
        try:
            return store.load_all_tickets(type_filter=self._filter_type)
        except FileNotFoundError:
            return []

    def _load_board(self) -> None:
        tickets = self._load_tickets()
        hierarchy = _build_hierarchy(tickets)

        # bucket all tickets by status for counting
        all_by_status: dict[str, int] = {"backlog": 0, "in-progress": 0, "done": 0}
        for t in tickets:
            if t.status in all_by_status:
                all_by_status[t.status] += 1

        for col_id, status in [("col-backlog", "backlog"), ("col-progress", "in-progress"), ("col-done", "done")]:
            opts = self.query_one(f"#opts-{col_id}", OptionList)
            opts.clear_options()

            header_widget = self.query_one(f"#{col_id} .column-header", Static)
            label = {"backlog": "BACKLOG", "in-progress": "IN PROGRESS", "done": "DONE"}[status]
            header_widget.update(f"{label} ({all_by_status[status]})")

            for group in hierarchy:
                epic = group["epic"]
                child_tasks = group["tasks"]

                # collect items in this status column for this group
                epic_in_col = epic and epic.status == status
                tasks_in_col = []
                for tn in child_tasks:
                    if tn["task"].status == status:
                        subs = [s for s in tn["subtasks"] if s.status == status]
                        tasks_in_col.append((tn["task"], subs))
                    else:
                        # subtasks might be in this column even if parent task isn't
                        subs = [s for s in tn["subtasks"] if s.status == status]
                        if subs:
                            tasks_in_col.append((None, subs))

                if not epic_in_col and not tasks_in_col:
                    continue

                # render epic header
                if epic:
                    if epic_in_col:
                        epic_card = (
                            f"[bold white on rgb(40,60,120)] EPIC [/] "
                            f"[bold]{epic.id}[/]\n"
                            f"[bold]{epic.title}[/]\n"
                            f"{_assignee_badge(epic)} "
                            f"[{PRIORITY_COLORS.get(epic.priority, 'white')}]{epic.priority}[/]"
                        )
                        if epic.labels:
                            epic_card += f"\n[dim]{' '.join('#' + l for l in epic.labels)}[/]"
                        opts.add_option(Option(epic_card, id=epic.id))
                    else:
                        # epic is in another column, show a dim reference header
                        opts.add_option(Option(
                            f"[dim bold]── {epic.id}: {epic.title} ──[/]",
                            id=epic.id,
                        ))

                # render tasks under this epic
                for task, subs in tasks_in_col:
                    if task:
                        assignee = _assignee_badge(task)
                        card = (
                            f"  [bold]{task.id}[/]\n"
                            f"  {task.title}\n"
                            f"  {assignee} "
                            f"[{PRIORITY_COLORS.get(task.priority, 'white')}]{task.priority}[/]"
                        )
                        if task.labels:
                            card += f"\n  [dim]{' '.join('#' + l for l in task.labels)}[/]"
                        opts.add_option(Option(card, id=task.id))

                    for sub in subs:
                        sub_card = (
                            f"    [dim]{sub.id}[/]\n"
                            f"    [dim]{sub.title}[/]\n"
                            f"    {_assignee_badge(sub)} "
                            f"[dim][{PRIORITY_COLORS.get(sub.priority, 'white')}]{sub.priority}[/][/]"
                        )
                        opts.add_option(Option(sub_card, id=sub.id))

        self._update_status("Board view loaded")

    def _load_list(self) -> None:
        tickets = self._load_tickets()
        hierarchy = _build_hierarchy(tickets)
        table = self.query_one("#ticket-table", DataTable)
        table.clear()
        count = 0

        for group in hierarchy:
            epic = group["epic"]

            if epic:
                title = epic.title if len(epic.title) <= 43 else epic.title[:40] + "..."
                assignee = ""
                if epic.assignee:
                    assignee = f"{epic.assignee} ({epic.assignee_type})" if epic.assignee_type else epic.assignee
                table.add_row(
                    epic.id, "EPIC", epic.status, epic.priority,
                    assignee, f">> {title}", key=epic.id,
                )
                count += 1

            for tn in group["tasks"]:
                task = tn["task"]
                title = task.title if len(task.title) <= 41 else task.title[:38] + "..."
                assignee = ""
                if task.assignee:
                    assignee = f"{task.assignee} ({task.assignee_type})" if task.assignee_type else task.assignee
                prefix = "├─ " if epic else ""
                table.add_row(
                    task.id, "task", task.status, task.priority,
                    assignee, f"{prefix}{title}", key=task.id,
                )
                count += 1

                for sub in tn["subtasks"]:
                    stitle = sub.title if len(sub.title) <= 39 else sub.title[:36] + "..."
                    sassignee = ""
                    if sub.assignee:
                        sassignee = f"{sub.assignee} ({sub.assignee_type})" if sub.assignee_type else sub.assignee
                    table.add_row(
                        sub.id, "subtask", sub.status, sub.priority,
                        sassignee, f"│  ├─ {stitle}", key=sub.id,
                    )
                    count += 1

        self._update_status(f"{count} ticket(s)")

    def _show_detail(self, ticket_id: str) -> None:
        self._selected_ticket_id = ticket_id
        try:
            ticket = store.load_ticket(ticket_id)
            md = _ticket_detail_md(ticket)
            self.query_one("#detail-md", Markdown).update(md)
            panel = self.query_one("#detail-panel")
            panel.display = True
            self._apply_detail_layout()
            self._update_status(f"Viewing {ticket_id} | c=comment  m=move  Escape=close")
        except FileNotFoundError:
            self._update_status(f"Ticket {ticket_id} not found")

    def _hide_detail(self) -> None:
        self.query_one("#detail-panel").display = False
        self._selected_ticket_id = None
        self._apply_detail_layout()
        self._update_status("")

    def _apply_detail_layout(self) -> None:
        """On narrow terminals the open detail panel takes the whole width."""
        detail_open = self.query_one("#detail-panel").display
        narrow = self.size.width < NARROW_TERMINAL_WIDTH
        view_container = {"board": "#board-container", "list": "#list-container", "snapshot": "#snapshot-container"}
        container = self.query_one(view_container[self._current_view])
        container.display = not (detail_open and narrow)

    def on_resize(self) -> None:
        if self._selected_ticket_id:
            self._apply_detail_layout()

    def _update_status(self, msg: str) -> None:
        filt = f" | filter: {self._filter_type}" if self._filter_type else ""
        self.query_one("#status-bar", Static).update(f" {msg}{filt}")

    # ── Event handlers ────────────────────────────────────────────────

    @on(OptionList.OptionSelected, ".board-column OptionList")
    def board_card_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self._show_detail(event.option.id)

    @on(DataTable.RowSelected, "#ticket-table")
    def table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            self._show_detail(str(event.row_key.value))

    @on(OptionList.OptionSelected, "#project-list")
    def project_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            store.set_active_project(event.option.id)
            store.set_project_override(event.option.id)
            try:
                config = store.load_config()
                name = config.get("project_name", event.option.id)
                self.sub_title = f"{name} ({event.option.id})"
            except FileNotFoundError:
                self.sub_title = event.option.id
            self._hide_project_switcher()
            self.action_refresh()

    def key_escape(self) -> None:
        if self.query_one("#detail-panel").display:
            self._hide_detail()
        elif self.query_one("#project-switcher").display:
            self._hide_project_switcher()

    def key_c(self) -> None:
        if self._selected_ticket_id:
            self.push_screen(CommentModal(self._selected_ticket_id), self._on_modal_dismiss)

    def key_m(self) -> None:
        if self._selected_ticket_id:
            try:
                ticket = store.load_ticket(self._selected_ticket_id)
                self.push_screen(MoveModal(self._selected_ticket_id, ticket.status), self._on_modal_dismiss)
            except FileNotFoundError:
                pass

    def _on_modal_dismiss(self, result: str | None) -> None:
        if result:
            self._update_status(result)
        self.action_refresh()
        if self._selected_ticket_id:
            self._show_detail(self._selected_ticket_id)

    # ── Actions ───────────────────────────────────────────────────────

    def action_view_board(self) -> None:
        self._current_view = "board"
        self._hide_detail()
        self.query_one("#board-container").display = True
        self.query_one("#list-container").display = False
        self.query_one("#snapshot-container").display = False
        self.query_one("#project-switcher").display = False
        self._load_board()

    def action_view_list(self) -> None:
        self._current_view = "list"
        self._hide_detail()
        self.query_one("#board-container").display = False
        self.query_one("#list-container").display = True
        self.query_one("#snapshot-container").display = False
        self.query_one("#project-switcher").display = False
        self._load_list()

    def action_view_snapshot(self) -> None:
        self._current_view = "snapshot"
        self._hide_detail()
        self.query_one("#board-container").display = False
        self.query_one("#list-container").display = False
        self.query_one("#snapshot-container").display = True
        self.query_one("#project-switcher").display = False
        try:
            text = generate_snapshot()
            self.query_one("#snapshot-md", Markdown).update(text)
            self._update_status("Snapshot loaded")
        except FileNotFoundError as e:
            self.query_one("#snapshot-md", Markdown).update(f"Error: {e}")

    def action_switch_project(self) -> None:
        self._hide_detail()
        self.query_one("#board-container").display = False
        self.query_one("#list-container").display = False
        self.query_one("#snapshot-container").display = False
        switcher = self.query_one("#project-switcher")
        switcher.display = True

        opts = self.query_one("#project-list", OptionList)
        opts.clear_options()
        active = store.get_active_project()
        for p in store.list_projects():
            marker = "-> " if p["slug"] == active else "   "
            opts.add_option(Option(f"{marker}{p['name']} ({p['slug']})", id=p["slug"]))
        opts.focus()

    def _hide_project_switcher(self) -> None:
        self.query_one("#project-switcher").display = False
        if self._current_view == "board":
            self.action_view_board()
        elif self._current_view == "list":
            self.action_view_list()
        elif self._current_view == "snapshot":
            self.action_view_snapshot()

    def action_cycle_filter(self) -> None:
        self._filter_idx = (self._filter_idx + 1) % len(self._filter_cycle)
        self._filter_type = self._filter_cycle[self._filter_idx]
        self.action_refresh()

    def action_refresh(self) -> None:
        if self._current_view == "board":
            self._load_board()
        elif self._current_view == "list":
            self._load_list()
        elif self._current_view == "snapshot":
            self.action_view_snapshot()


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="kbtui", description="kb TUI")
    parser.add_argument("--project", "-P", help="Project slug", metavar="SLUG")
    parser.add_argument(
        "--view", choices=["board", "list", "snapshot"], default="board",
        help="View to open first (default: board)",
    )
    args = parser.parse_args()

    app = KanbanApp(project_slug=args.project, initial_view=args.view)
    app.run()


if __name__ == "__main__":
    main()
