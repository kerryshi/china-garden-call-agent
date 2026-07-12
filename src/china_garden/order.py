"""Order state + the mandatory read-back. Money is integer cents."""

from __future__ import annotations

from dataclasses import dataclass, field

from .menu import MenuItem, Size
from .money import fmt_cents


@dataclass
class OrderLine:
    item: MenuItem
    size: Size
    qty: int
    notes: str = ""

    @property
    def line_total_cents(self) -> int:
        return self.size.price_cents * self.qty

    def describe(self) -> str:
        size_part = f"{self.size.name} " if self.size.name else ""
        note_part = f" ({self.notes})" if self.notes else ""
        return f"{self.qty} {size_part}{self.item.name}{note_part}"


@dataclass
class Order:
    sales_tax_bps: int
    lines: list[OrderLine] = field(default_factory=list)

    def add(self, item: MenuItem, qty: int = 1, size_name: str | None = None,
            notes: str = "") -> OrderLine:
        size = (item.size_named(size_name) if size_name else None) or item.default_size
        for line in self.lines:
            if line.item.id == item.id and line.size.name == size.name and line.notes == notes:
                line.qty += qty
                return line
        line = OrderLine(item=item, size=size, qty=qty, notes=notes)
        self.lines.append(line)
        return line

    def find_line(self, query_item: MenuItem,
                  size_name: str | None = None) -> OrderLine | None:
        matches = [line for line in self.lines if line.item.id == query_item.id]
        if size_name:
            sized = [line for line in matches if line.size.name == size_name]
            if sized:
                return sized[0]
        return matches[0] if matches else None

    def remove(self, line: OrderLine) -> None:
        self.lines.remove(line)

    @property
    def subtotal_cents(self) -> int:
        return sum(line.line_total_cents for line in self.lines)

    @property
    def tax_cents(self) -> int:
        # round-half-up in integer math: bps = basis points (675 = 6.75%)
        return (self.subtotal_cents * self.sales_tax_bps + 5000) // 10000

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.tax_cents

    def summary(self) -> list[dict[str, str | int]]:
        """Compact, caller-safe snapshot for a human handoff briefing."""
        return [
            {"item": line.item.name, "qty": line.qty, "size": line.size.name,
             "notes": line.notes}
            for line in self.lines
        ]

    def read_back(self) -> str:
        """The confirmation script: every line, then the total. Never skipped."""
        if not self.lines:
            return "Your order is empty."
        parts = ["Let me read that back:"]
        for line in self.lines:
            parts.append(f"  {line.describe()} - {fmt_cents(line.line_total_cents)}")
        parts.append(
            f"That's {fmt_cents(self.subtotal_cents)} plus tax, "
            f"{fmt_cents(self.total_cents)} total."
        )
        return "\n".join(parts)
