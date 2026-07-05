"""Menu model. All offerings live in data/menu.json, never in code."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# tokens that change WHICH dish is meant - a mismatch means "ask, don't guess"
_QUALIFIERS = {"pork", "beef", "shrimp", "chicken", "vegetable", "veggie",
               "brown", "white", "tofu"}


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

    def find_exact(self, query: str) -> MenuItem | None:
        q = _norm(query)
        if not q:
            return None
        for item in self.items:
            if q == _norm(item.name) or any(q == _norm(a) for a in item.aliases):
                return item
        return None

    def find(self, query: str) -> MenuItem | None:
        """Fuzzy lookup: exact name/alias, then token-subset, then substring.

        Guards (2026-07-05 review): a subset match needs >=2 shared tokens
        (single shared tokens matched 'no' -> Chicken Lo Mein, 'pork fried
        rice' -> White Rice), a protein/qualifier mismatch rejects the
        candidate ('shrimp lo mein' must not become Chicken Lo Mein), and the
        substring fallback only runs query-inside-candidate with >=4 chars.
        """
        exact = self.find_exact(query)
        if exact:
            return exact
        q = _norm(query)
        if not q:
            return None
        q_tokens = set(q.split())
        q_qual = q_tokens & _QUALIFIERS
        best: tuple[int, MenuItem] | None = None
        for item in self.items:
            for cand in (item.name, *item.aliases):
                c_tokens = set(_norm(cand).split())
                if not (q_tokens <= c_tokens or c_tokens <= q_tokens):
                    continue
                shared = q_tokens & c_tokens
                if len(shared) < 2:
                    continue
                if q_qual and q_qual != (c_tokens & _QUALIFIERS):
                    continue  # protein/qualifier swap - ask, don't guess
                if best is None or len(shared) > best[0]:
                    best = (len(shared), item)
        if best:
            return best[1]
        if len(q) >= 4:
            hits = {item.id: item for item in self.items
                    if any(q in _norm(cand) for cand in (item.name, *item.aliases))}
            if len(hits) == 1:
                # a substring shared by several dishes ("chicken") is
                # ambiguous - ask, don't guess
                return next(iter(hits.values()))
        return None
