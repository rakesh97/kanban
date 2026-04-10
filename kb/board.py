"""ASCII kanban board rendering."""

import os
from typing import List

from .models import Ticket


def render_board(tickets: List[Ticket], title: str = "") -> str:
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 100

    backlog = [t for t in tickets if t.status == "backlog"]
    in_progress = [t for t in tickets if t.status == "in-progress"]
    done = [t for t in tickets if t.status == "done"]

    col_w = max(24, (term_width - 4) // 3)

    lines: List[str] = []

    if title:
        total_w = col_w * 3 + 4
        lines.append("=" * total_w)
        lines.append(f" {title} ".center(total_w))
        lines.append("=" * total_w)

    sep = "+" + "-" * col_w + "+" + "-" * col_w + "+" + "-" * col_w + "+"
    lines.append(sep)

    h1 = f" BACKLOG ({len(backlog)})"
    h2 = f" IN PROGRESS ({len(in_progress)})"
    h3 = f" DONE ({len(done)})"
    lines.append(f"|{h1:<{col_w}}|{h2:<{col_w}}|{h3:<{col_w}}|")
    lines.append(sep)

    max_cards = max(len(backlog), len(in_progress), len(done), 1)
    empty = [" " * col_w]

    for i in range(max_cards):
        c1 = _format_card(backlog[i], col_w) if i < len(backlog) else empty
        c2 = _format_card(in_progress[i], col_w) if i < len(in_progress) else empty
        c3 = _format_card(done[i], col_w) if i < len(done) else empty

        max_h = max(len(c1), len(c2), len(c3))
        c1 = _pad(c1, max_h, col_w)
        c2 = _pad(c2, max_h, col_w)
        c3 = _pad(c3, max_h, col_w)

        for j in range(max_h):
            lines.append(f"|{c1[j]}|{c2[j]}|{c3[j]}|")

        if i < max_cards - 1:
            thin = "|" + "." * col_w + "|" + "." * col_w + "|" + "." * col_w + "|"
            lines.append(thin)

    lines.append(sep)
    return "\n".join(lines)


def _pad(card_lines: List[str], height: int, width: int) -> List[str]:
    while len(card_lines) < height:
        card_lines.append(" " * width)
    return card_lines


def _format_card(ticket: Ticket, width: int) -> List[str]:
    w = width - 2  # 1-char padding each side
    lines: List[str] = []

    # ticket id
    tid = ticket.id
    if len(tid) > w:
        tid = tid[: w - 1] + "~"
    lines.append(f" {tid:<{w}} ")

    # title
    title = ticket.title
    if len(title) > w:
        title = title[: w - 3] + "..."
    lines.append(f" {title:<{w}} ")

    # assignee + priority
    if ticket.assignee:
        atype = f"{ticket.assignee_type}:" if ticket.assignee_type else ""
        assignee = f"{atype}{ticket.assignee}"
    else:
        assignee = "unassigned"
    pri = f"[{ticket.priority}]"
    meta = f"{assignee} {pri}"
    if len(meta) > w:
        meta = meta[: w - 3] + "..."
    lines.append(f" {meta:<{w}} ")

    # labels (compact)
    if ticket.labels:
        lbl = " ".join(f"#{l}" for l in ticket.labels)
        if len(lbl) > w:
            lbl = lbl[: w - 3] + "..."
        lines.append(f" {lbl:<{w}} ")

    # blank trailing line
    lines.append(" " * width)
    return lines
