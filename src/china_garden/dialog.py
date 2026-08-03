"""The turn state machine. Every reply carries the state; the caller stays dumb.

States: GREET -> OPEN -> ORDERING -> READ_BACK -> CONFIRMED | HANDOFF
The read-back is mandatory: no path reaches CONFIRMED without it.

Replies render in the caller's language: a turn containing CJK is answered in
Chinese, otherwise English (per turn - the caller can switch mid-call).
Templates live in strings.py; the English ones are pinned by the suite.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import faq as faq_mod
from .backends import Context, Intent, LLMBackend, has_cjk
from .faq import Restaurant
from .menu import Menu, price_text, size_zh
from .order import Order
from .strings import t
from .ticket import format_ticket


@dataclass
class Reply:
    text: str
    state: str
    done: bool = False
    order_summary: list[dict] | None = None


class DialogSession:
    def __init__(self, menu: Menu, restaurant: Restaurant, backend: LLMBackend):
        self.menu = menu
        self.restaurant = restaurant
        self.backend = backend
        self.order = Order(sales_tax_bps=restaurant.sales_tax_bps)
        self.state = "OPEN"
        self.lang = "en"

    def greeting(self) -> str:
        return self.restaurant.ai_disclosure

    def handle(self, utterance: str) -> Reply:
        self.lang = "zh" if has_cjk(utterance) else "en"
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
                return Reply("\n".join(x for x in texts if x), self.state, reply.done,
                             order_summary=reply.order_summary)
            if self.state == "READ_BACK" and context.state != "READ_BACK":
                # entered READ_BACK this turn: the caller has not heard the
                # read-back yet, so any further intents (e.g. a same-utterance
                # "confirm" from an LLM backend) must wait for their answer
                break
        return Reply("\n".join(x for x in texts if x), self.state)

    def _t(self, key: str, **kwargs: object) -> str:
        return t(self.lang, key, **kwargs)

    def _size_options(self, item) -> str:
        if self.lang == "zh":
            return "或".join(size_zh(s.name) for s in item.sizes)
        return " or ".join(s.name for s in item.sizes)

    def _handoff(self, message: str) -> Reply:
        self.state = "HANDOFF"
        order_summary = self.order.summary() if self.order.lines else None
        text = message
        if order_summary:
            text += self._t("saved_order_suffix")
        return Reply(text, self.state, done=True, order_summary=order_summary)

    def _apply(self, intent: Intent) -> Reply:
        if intent.kind == "allergen":
            return self._handoff(self.restaurant.policy("allergen_policy", self.lang))
        if intent.kind == "request_human":
            return self._handoff(self._t("handoff_person"))
        if intent.kind == "goodbye":
            if self.order.lines and self.state != "CONFIRMED":
                # never let a caller hang up believing an unplaced order exists
                self.state = "READ_BACK"
                return Reply(
                    self._t("goodbye_unplaced",
                            read_back=self.order.read_back(self.lang)),
                    self.state)
            return Reply(self._t("goodbye", name=self.restaurant.name), self.state,
                         done=True)
        if intent.kind == "faq":
            return Reply(faq_mod.answer(intent.topic, self.restaurant, self.lang),
                         self.state)

        if intent.kind == "item_price":
            item = self.menu.find(intent.item_query)
            if not item:
                return Reply(self._t("price_unsure"), self.state)
            return Reply(price_text(item, self.lang), self.state)

        if intent.kind == "add_item":
            item = self.menu.find(intent.item_query)
            if not item:
                return Reply(self._t("unknown_item", query=intent.item_query),
                             self.state)
            if intent.size and item.sizes[0].name and not item.size_named(intent.size):
                return Reply(self._t("size_choice", name=item.display_name(self.lang),
                                     options=self._size_options(item)), self.state)
            if intent.qty > 20:
                # an STT mis-hear shouldn't silently create a $7,000 order
                return Reply(self._t("qty_check", qty=intent.qty,
                                     name=item.display_name(self.lang)), self.state)
            line = self.order.add(item, qty=intent.qty,
                                  size_name=intent.size or None, notes=intent.notes)
            self.state = "ORDERING"
            return Reply(self._t("added", desc=line.describe(self.lang)), self.state)

        if intent.kind == "remove_item":
            item = self.menu.find(intent.item_query)
            line = self.order.find_line(item, intent.size or None) if item else None
            if not line:
                return Reply(self._t("not_on_order"), self.state)
            self.order.remove(line)
            state = "ORDERING" if self.order.lines else "OPEN"
            self.state = state
            return Reply(self._t("removed", desc=line.describe(self.lang)), self.state)

        if intent.kind == "set_qty":
            line = None
            if intent.item_query:
                item = self.menu.find(intent.item_query)
                line = self.order.find_line(item, intent.size or None) if item else None
            elif self.order.lines:
                line = self.order.lines[-1]
            if not line:
                return Reply(self._t("which_change"), self.state)
            if intent.qty <= 0:
                self.order.remove(line)
                self.state = "ORDERING" if self.order.lines else "OPEN"
                return Reply(self._t("removed_name",
                                     name=line.item.display_name(self.lang)),
                             self.state)
            line.qty = intent.qty
            self.state = "ORDERING"
            return Reply(self._t("okay", desc=line.describe(self.lang)), self.state)

        if intent.kind == "done_ordering":
            if not self.order.lines:
                return Reply(self._t("nothing_yet"), self.state)
            self.state = "READ_BACK"
            return Reply(self._t("read_back_q",
                                 read_back=self.order.read_back(self.lang)),
                         self.state)

        if intent.kind == "confirm" and self.state == "READ_BACK":
            self.state = "CONFIRMED"
            return Reply(
                self._t("confirmed", eta=self.restaurant.pickup_minutes,
                        ticket=format_ticket(self.order)),
                self.state, done=True)

        if intent.kind == "deny" and self.state == "READ_BACK":
            self.state = "ORDERING"
            return Reply(self._t("fix_what"), self.state)

        return Reply(self._t("fallback"), self.state)
