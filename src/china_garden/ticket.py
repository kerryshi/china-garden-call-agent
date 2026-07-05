"""Kitchen ticket - plain text, printer-width. Prototyped early by design."""

from __future__ import annotations

from datetime import datetime

from .money import fmt_cents
from .order import Order

WIDTH = 32


def format_ticket(order: Order, when: datetime | None = None) -> str:
    when = when or datetime.now()
    lines = [
        "=" * WIDTH,
        "PICKUP ORDER".center(WIDTH),
        when.strftime("%a %b %d  %I:%M %p").center(WIDTH),
        "-" * WIDTH,
    ]
    for line in order.lines:
        qty_part = f"{line.qty} x "
        size_part = f"{line.size.name} " if line.size.name else ""
        lines.append(f"{qty_part}{size_part}{line.item.name}")
        if line.notes:
            lines.append(f"    ** {line.notes.upper()} **")
    lines += [
        "-" * WIDTH,
        f"TOTAL {fmt_cents(order.total_cents)}".rjust(WIDTH),
        "=" * WIDTH,
    ]
    return "\n".join(lines)
