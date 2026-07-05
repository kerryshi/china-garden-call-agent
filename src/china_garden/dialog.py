"""The turn state machine. Every reply carries the state; the caller stays dumb.

States: GREET -> OPEN -> ORDERING -> READ_BACK -> CONFIRMED | HANDOFF
The read-back is mandatory: no path reaches CONFIRMED without it.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import faq as faq_mod
from .backends import Context, Intent, LLMBackend
from .faq import Restaurant
from .menu import Menu
from .order import Order
from .ticket import format_ticket


@dataclass
class Reply:
    text: str
    state: str
    done: bool = False


class DialogSession:
    def __init__(self, menu: Menu, restaurant: Restaurant, backend: LLMBackend):
        self.menu = menu
        self.restaurant = restaurant
        self.backend = backend
        self.order = Order(sales_tax_bps=restaurant.sales_tax_bps)
        self.state = "OPEN"

    def greeting(self) -> str:
        return self.restaurant.ai_disclosure

    def handle(self, utterance: str) -> Reply:
        context = Context(
            state=self.state,
            order_item_ids=[line.item.id for line in self.order.lines],
        )
        intents = self.backend.parse(utterance, context)
        texts: list[str] = []
        for intent in intents:
            reply = self._apply(intent)
            texts.append(reply.text)
            if reply.done or self.state == "HANDOFF":
                return Reply("\n".join(t for t in texts if t), self.state, reply.done)
        return Reply("\n".join(t for t in texts if t), self.state)

    def _apply(self, intent: Intent) -> Reply:
        if intent.kind == "allergen":
            self.state = "HANDOFF"
            return Reply(self.restaurant.allergen_policy, self.state, done=True)
        if intent.kind == "request_human":
            self.state = "HANDOFF"
            return Reply("No problem - one moment while I get a person for you.",
                         self.state, done=True)
        if intent.kind == "goodbye":
            return Reply("Thanks for calling China Garden - bye now!", self.state,
                         done=True)
        if intent.kind == "faq":
            return Reply(faq_mod.answer(intent.topic, self.restaurant), self.state)

        if intent.kind == "add_item":
            item = self.menu.find(intent.item_query)
            if not item:
                return Reply(
                    f"Sorry, I couldn't find '{intent.item_query}' on our menu - "
                    "could you say it another way?", self.state)
            line = self.order.add(item, qty=intent.qty,
                                  size_name=intent.size or None, notes=intent.notes)
            self.state = "ORDERING"
            return Reply(f"Got it - {line.describe()}. Anything else?", self.state)

        if intent.kind == "remove_item":
            item = self.menu.find(intent.item_query)
            line = self.order.find_line(item) if item else None
            if not line:
                return Reply("I don't see that on your order - what should I remove?",
                             self.state)
            self.order.remove(line)
            state = "ORDERING" if self.order.lines else "OPEN"
            self.state = state
            return Reply(f"Removed {line.item.name}. Anything else?", self.state)

        if intent.kind == "done_ordering":
            if not self.order.lines:
                return Reply("I don't have anything on your order yet - what can I "
                             "get started for you?", self.state)
            self.state = "READ_BACK"
            return Reply(self.order.read_back() + "\nIs that all correct?", self.state)

        if intent.kind == "confirm" and self.state == "READ_BACK":
            self.state = "CONFIRMED"
            eta = self.restaurant.pickup_minutes
            return Reply(
                f"You're all set - it'll be ready for pickup in about {eta} minutes. "
                f"See you soon!\n{format_ticket(self.order)}",
                self.state, done=True)

        if intent.kind == "deny" and self.state == "READ_BACK":
            self.state = "ORDERING"
            return Reply("Sorry about that - what should I fix?", self.state)

        return Reply("Sorry, I didn't catch that - you can order, ask about hours "
                     "or delivery, or say 'person' for a human.", self.state)
