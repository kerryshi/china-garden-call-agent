"""Intent parsing behind a swappable backend.

RuleBackend is deterministic and is what tests (and the default CLI) use.
HaikuBackend calls cloud Claude Haiku via forced tool use; it is constructed
only when explicitly selected and requires the [llm] extra + credentials.
Tests must never depend on a live API call (AGENTS.md rule).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .menu import Menu

KINDS = (
    "add_item", "remove_item", "set_qty", "done_ordering", "confirm", "deny",
    "faq", "allergen", "request_human", "goodbye", "unknown",
)
FAQ_TOPICS = ("hours", "address", "phone", "delivery", "payment")

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_SIZE_WORDS = {"pint": "pint", "quart": "quart", "small": "pint", "large": "quart"}


@dataclass
class Intent:
    kind: str
    item_query: str = ""
    qty: int = 1
    size: str = ""
    notes: str = ""
    topic: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            self.kind = "unknown"


@dataclass
class Context:
    """What the parser may need to disambiguate: dialog state + order contents."""
    state: str = "OPEN"
    order_item_ids: list[str] = field(default_factory=list)


class LLMBackend(Protocol):
    def parse(self, utterance: str, context: Context) -> list[Intent]: ...


class RuleBackend:
    """Keyword/pattern parser - deterministic, offline, the test baseline."""

    def __init__(self, menu: Menu):
        self.menu = menu

    def parse(self, utterance: str, context: Context) -> list[Intent]:
        text = utterance.lower().strip()
        if not text:
            return [Intent("unknown")]

        if re.search(r"\b(allerg|peanut|gluten|shellfish|msg)\w*", text):
            return [Intent("allergen")]
        if re.search(r"\b(person|human|manager|operator|somebody|someone real)\b", text):
            return [Intent("request_human")]
        if re.search(r"\b(bye|goodbye|thank you, bye|that's everything, bye)\b", text):
            return [Intent("goodbye")]

        for topic, pattern in (
            ("hours", r"\b(hours?|open|close|closing|opening)\b"),
            ("delivery", r"\bdeliver\w*|door ?dash|grub ?hub\b"),
            ("payment", r"\b(pay|payment|card|credit|cash|apple pay)\b"),
            ("address", r"\b(address|where are you|located|location)\b"),
            ("phone", r"\b(phone number|number)\b"),
        ):
            if re.search(pattern, text):
                return [Intent("faq", topic=topic)]

        if context.state == "READ_BACK":
            if re.search(r"\b(yes|yeah|yep|correct|right|that's it|sounds good|good)\b", text):
                return [Intent("confirm")]
            if re.search(r"\b(no|nope|wrong|not right|actually)\b", text):
                return [Intent("deny")]

        if re.search(r"\b(that's (it|all)|that is (it|all)|nothing else|i'?m done|done)\b", text):
            return [Intent("done_ordering")]

        removal = re.search(r"\b(remove|take off|cancel|no more|drop|scratch)\b(.*)", text)
        if removal and context.state in ("ORDERING", "OPEN"):
            item = self.menu.find(removal.group(2))
            if item:
                return [Intent("remove_item", item_query=item.name)]

        intents = self._parse_items(text)
        if intents:
            return intents
        return [Intent("unknown")]

    def _parse_items(self, text: str) -> list[Intent]:
        intents: list[Intent] = []
        for chunk in re.split(r"\band\b|,", text):
            chunk = chunk.strip()
            if not chunk:
                continue
            qty = 1
            m = re.search(r"\b(\d+)\b", chunk)
            if m:
                qty = int(m.group(1))
            else:
                for word, n in _NUMBER_WORDS.items():
                    if re.search(rf"\b{word}\b", chunk):
                        qty = n
                        break
            size = ""
            for word, canonical in _SIZE_WORDS.items():
                if re.search(rf"\b{word}\b", chunk):
                    size = canonical
                    break
            notes = ""
            note_match = re.search(r"\b(extra \w+|no \w+|spicy|mild)\b", chunk)
            if note_match and not self.menu.find(note_match.group(1)):
                notes = note_match.group(1)
            item = self.menu.find(
                re.sub(r"\b(\d+|" + "|".join(_NUMBER_WORDS) + r"|"
                       + "|".join(_SIZE_WORDS) + r"|of|the|please|i'?d like|i want|"
                       r"can i (get|have)|get|order|extra \w+|no \w+|spicy|mild)\b",
                       " ", chunk).strip()
            )
            if item:
                intents.append(Intent("add_item", item_query=item.name, qty=qty,
                                      size=size, notes=notes))
            elif notes and intents:
                # a chunk that is only a note ("..., extra spicy") belongs to
                # the item before the comma, not to a new intent
                prev = intents[-1]
                prev.notes = f"{prev.notes} {notes}".strip()
        return intents


HAIKU_MODEL = "claude-haiku-4-5"

_INTENT_TOOL = {
    "name": "record_intents",
    "description": (
        "Record the caller's parsed intent(s) from their latest utterance on a "
        "restaurant phone line. Use one intent per distinct request. Only use "
        "item names that plausibly match the menu; never invent menu items. Any "
        "allergy or ingredient-safety question is kind=allergen. Any request to "
        "talk to a person is kind=request_human."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "intents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": list(KINDS)},
                        "item_query": {"type": "string"},
                        "qty": {"type": "integer"},
                        "size": {"type": "string", "enum": ["", "pint", "quart"]},
                        "notes": {"type": "string"},
                        "topic": {"type": "string", "enum": ["", *FAQ_TOPICS]},
                    },
                    "required": ["kind", "item_query", "qty", "size", "notes", "topic"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["intents"],
        "additionalProperties": False,
    },
}


class HaikuBackend:
    """Cloud Claude Haiku intent parser via forced tool use.

    Lazy import: the anthropic SDK lives in the [llm] extra so the core
    package and tests carry no API dependency.
    """

    def __init__(self, menu: Menu, client=None):
        if client is None:
            try:
                import anthropic
            except ImportError as e:
                raise RuntimeError(
                    "HaikuBackend needs the [llm] extra: pip install -e .[llm]"
                ) from e
            client = anthropic.Anthropic()
        self.client = client
        self.menu = menu
        item_lines = "\n".join(
            f"- {it.name}" + (f" (sizes: {', '.join(s.name for s in it.sizes)})"
                              if it.sizes[0].name else "")
            for it in menu.items
        )
        self._system = (
            "You parse a single caller utterance from a Chinese-takeout phone "
            "line into structured intents. The menu is:\n" + item_lines + "\n"
            "Rules: one intent per distinct request; qty defaults to 1; size is "
            "'' unless the caller names one; allergy/ingredient-safety questions "
            "are kind=allergen (never answer them); requests for a person are "
            "kind=request_human; in the READ_BACK state a plain agreement is "
            "kind=confirm and a correction is kind=deny."
        )

    def parse(self, utterance: str, context: Context) -> list[Intent]:
        response = self.client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            system=self._system,
            tools=[_INTENT_TOOL],
            tool_choice={"type": "tool", "name": "record_intents"},
            messages=[{
                "role": "user",
                "content": f"Dialog state: {context.state}\nCaller said: {utterance}",
            }],
        )
        for block in response.content:
            if block.type == "tool_use":
                raw = block.input.get("intents", [])
                intents = [
                    Intent(
                        kind=i.get("kind", "unknown"),
                        item_query=i.get("item_query", ""),
                        qty=max(1, int(i.get("qty", 1))),
                        size=i.get("size", ""),
                        notes=i.get("notes", ""),
                        topic=i.get("topic", ""),
                    )
                    for i in raw
                ]
                return intents or [Intent("unknown")]
        return [Intent("unknown")]
