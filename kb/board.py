"""ASCII kanban board rendering.

The board adapts to the terminal width: three side-by-side columns when
there is room, otherwise one full-width section per status stacked
vertically. No rendered line is ever wider than the terminal.
"""

import os
import shutil
import textwrap
from typing import List, Optional, Sequence, Tuple

from .models import Ticket

COLUMNS: Sequence[Tuple[str, str]] = (
    ("backlog", "BACKLOG"),
    ("in-progress", "IN PROGRESS"),
    ("done", "DONE"),
)

MIN_COLUMN_WIDTH = 24
MIN_BOARD_WIDTH = 20
FALLBACK_WIDTH = 100
TITLE_MAX_LINES = 2


def terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return shutil.get_terminal_size((FALLBACK_WIDTH, 24)).columns


def render_board(tickets: List[Ticket], title: str = "", width: Optional[int] = None) -> str:
    total_w = max(MIN_BOARD_WIDTH, width or terminal_width())
    buckets = [[t for t in tickets if t.status == status] for status, _ in COLUMNS]

    if _fits_side_by_side(total_w):
        return _render_columns(buckets, title, total_w)
    return _render_stacked(buckets, title, total_w)


def _fits_side_by_side(total_w: int) -> bool:
    return total_w >= MIN_COLUMN_WIDTH * len(COLUMNS) + len(COLUMNS) + 1


def _render_columns(buckets: List[List[Ticket]], title: str, total_w: int) -> str:
    n = len(COLUMNS)
    inner = total_w - (n + 1)
    col_w = inner // n
    widths = [col_w] * n
    widths[-1] += inner - col_w * n
    board_w = sum(widths) + n + 1

    lines: List[str] = []
    lines.extend(_title_lines(title, board_w))

    sep = "+" + "+".join("-" * w for w in widths) + "+"
    thin = "|" + "|".join("." * w for w in widths) + "|"
    lines.append(sep)
    headers = [
        _fit(f" {label} ({len(bucket)})", w)
        for (status, label), bucket, w in zip(COLUMNS, buckets, widths)
    ]
    lines.append("|" + "|".join(headers) + "|")
    lines.append(sep)

    max_cards = max([len(b) for b in buckets] + [1])
    for i in range(max_cards):
        cards = [
            _format_card(bucket[i], w) if i < len(bucket) else [" " * w]
            for bucket, w in zip(buckets, widths)
        ]
        height = max(len(c) for c in cards)
        cards = [_pad(c, height, w) for c, w in zip(cards, widths)]
        for j in range(height):
            lines.append("|" + "|".join(c[j] for c in cards) + "|")
        if i < max_cards - 1:
            lines.append(thin)

    lines.append(sep)
    return "\n".join(lines)


def _render_stacked(buckets: List[List[Ticket]], title: str, total_w: int) -> str:
    col_w = total_w - 2
    sep = "+" + "-" * col_w + "+"
    thin = "|" + "." * col_w + "|"

    lines: List[str] = []
    lines.extend(_title_lines(title, total_w))

    for (status, label), bucket in zip(COLUMNS, buckets):
        lines.append(sep)
        lines.append("|" + _fit(f" {label} ({len(bucket)})", col_w) + "|")
        lines.append(sep)
        if not bucket:
            lines.append("|" + _fit(" (empty)", col_w) + "|")
        for i, ticket in enumerate(bucket):
            for row in _format_card(ticket, col_w):
                lines.append("|" + row + "|")
            if i < len(bucket) - 1:
                lines.append(thin)
    lines.append(sep)
    return "\n".join(lines)


def _title_lines(title: str, width: int) -> List[str]:
    if not title:
        return []
    wrapped = textwrap.wrap(title, max(1, width - 2)) or [""]
    if len(wrapped) > TITLE_MAX_LINES:
        wrapped = wrapped[:TITLE_MAX_LINES]
        wrapped[-1] = _truncate(wrapped[-1], width - 2)
    lines = ["=" * width]
    lines.extend(f" {t} ".center(width) for t in wrapped)
    lines.append("=" * width)
    return lines


def _pad(card_lines: List[str], height: int, width: int) -> List[str]:
    while len(card_lines) < height:
        card_lines.append(" " * width)
    return card_lines


def _fit(text: str, width: int) -> str:
    return f"{_truncate(text, width):<{width}}"


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _format_card(ticket: Ticket, width: int) -> List[str]:
    w = max(1, width - 2)
    lines: List[str] = []

    tid = ticket.id if len(ticket.id) <= w else ticket.id[: max(0, w - 1)] + "~"
    lines.append(f" {tid:<{w}} ")

    title_lines = textwrap.wrap(ticket.title, w) or [""]
    if len(title_lines) > TITLE_MAX_LINES:
        title_lines = title_lines[:TITLE_MAX_LINES]
        title_lines[-1] = _truncate(title_lines[-1] + "...", w)
    for t in title_lines:
        lines.append(f" {t:<{w}} ")

    if ticket.assignee:
        atype = f"{ticket.assignee_type}:" if ticket.assignee_type else ""
        assignee = f"{atype}{ticket.assignee}"
    else:
        assignee = "unassigned"
    lines.append(f" {_fit(f'{assignee} [{ticket.priority}]', w)} ")

    if ticket.labels:
        lbl = " ".join(f"#{l}" for l in ticket.labels)
        lines.append(f" {_fit(lbl, w)} ")

    lines.append(" " * width)
    return lines
