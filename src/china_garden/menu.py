"""Menu model. All offerings live in data/menu.json, never in code."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


@dataclass(frozen=True)
class Size:
    name: str  # "" for single-size items
    price_cents: int


@dataclass(frozen=True)
class MenuItem:
    id: str
    name: str
    aliases: tuple[str, ...]
    sizes: tuple[Size, ...]
    note: str = ""

    @property
    def default_size(self) -> Size:
        return self.sizes[0]

    def size_named(self, name: str) -> Size | None:
        for s in self.sizes:
            if s.name == name:
                return s
        return None


class Menu:
    def __init__(self, items: list[MenuItem]):
        self.items = items

    @classmethod
    def load(cls, path: Path | None = None) -> Menu:
        raw = json.loads((path or DATA_DIR / "menu.json").read_text(encoding="utf-8"))
        items = [
            MenuItem(
                id=it["id"],
                name=it["name"],
                aliases=tuple(it.get("aliases", [])),
                sizes=tuple(Size(s["name"], s["price_cents"]) for s in it["sizes"]),
                note=it.get("note", ""),
            )
            for it in raw["items"]
        ]
        return cls(items)

    def find(self, query: str) -> MenuItem | None:
        """Fuzzy lookup: exact name/alias first, then token-subset, then substring."""
        q = _norm(query)
        if not q:
            return None
        for item in self.items:
            if q == _norm(item.name) or any(q == _norm(a) for a in item.aliases):
                return item
        q_tokens = set(q.split())
        best: tuple[int, MenuItem] | None = None
        for item in self.items:
            for cand in (item.name, *item.aliases):
                c_tokens = set(_norm(cand).split())
                if q_tokens and (q_tokens <= c_tokens or c_tokens <= q_tokens):
                    score = len(q_tokens & c_tokens)
                    if best is None or score > best[0]:
                        best = (score, item)
        if best:
            return best[1]
        for item in self.items:
            for cand in (item.name, *item.aliases):
                nc = _norm(cand)
                if q in nc or nc in q:
                    return item
        return None
