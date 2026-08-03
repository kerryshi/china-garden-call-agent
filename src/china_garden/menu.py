"""Menu model. All offerings live in data/menu.json, never in code."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .money import fmt_cents

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# tokens that change WHICH dish is meant - a mismatch means "ask, don't guess"
_QUALIFIERS = {"pork", "beef", "shrimp", "chicken", "vegetable", "veggie",
               "brown", "white", "tofu"}


def _norm(text: str) -> str:
    # keep CJK so Chinese names/aliases survive normalization
    return re.sub(r"[^a-z0-9一-鿿 ]", "", text.lower()).strip()


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


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
    name_zh: str = ""

    @property
    def default_size(self) -> Size:
        return self.sizes[0]

    def size_named(self, name: str) -> Size | None:
        for s in self.sizes:
            if s.name == name:
                return s
        return None

    def display_name(self, lang: str = "en") -> str:
        return self.name_zh if lang == "zh" and self.name_zh else self.name

    def match_candidates(self) -> tuple[str, ...]:
        cands = (self.name, self.name_zh, *self.aliases)
        return tuple(c for c in cands if c)


_SIZE_ZH = {"pint": "小份", "quart": "大份"}


def size_zh(name: str) -> str:
    return _SIZE_ZH.get(name, name)


def price_text(item: MenuItem, lang: str = "en") -> str:
    """Spoken price line - multi-size items state every size, never one guess."""
    if lang == "zh":
        if len(item.sizes) == 1 and not item.sizes[0].name:
            return f"{item.display_name('zh')}是{fmt_cents(item.sizes[0].price_cents)}。"
        sizes = "，".join(
            f"{size_zh(s.name)}{fmt_cents(s.price_cents)}" for s in item.sizes
        )
        return f"{item.display_name('zh')}是：{sizes}。"
    if len(item.sizes) == 1 and not item.sizes[0].name:
        return f"{item.name} is {fmt_cents(item.sizes[0].price_cents)}."
    sizes = ", ".join(
        f"{fmt_cents(s.price_cents)} for a {s.name}" for s in item.sizes
    )
    return f"{item.name} is {sizes}."


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
                name_zh=it.get("name_zh", ""),
            )
            for it in raw["items"]
        ]
        return cls(items)

    def find_exact(self, query: str) -> MenuItem | None:
        q = _norm(query)
        if not q:
            return None
        for item in self.items:
            if any(q == _norm(c) for c in item.match_candidates()):
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
            for cand in item.match_candidates():
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
        # CJK names are 2-4 chars, so the substring floor drops to 2 for them
        min_len = 2 if _has_cjk(q) else 4
        if len(q) >= min_len:
            hits = {item.id: item for item in self.items
                    if any(q in _norm(cand) for cand in item.match_candidates())}
            if len(hits) == 1:
                # a substring shared by several dishes ("chicken") is
                # ambiguous - ask, don't guess
                return next(iter(hits.values()))
        return None
