"""The turn state machine. Every reply carries the state; the caller stays dumb.

States: GREET -> OPEN -> ORDERING -> READ_BACK -> CONFIRMED | HANDOFF
The read-back is mandatory: no path reaches CONFIRMED without it.

Every reply is rendered in BOTH languages (text_en / text_zh) so the demo can
display them side by side; `text` is the caller's language for speaking (a
turn containing CJK is answered in Chinese, else English - per turn).
State mutates once per intent; only the rendering runs twice.
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

LANGS = ("en", "zh")


@dataclass
class Reply:
    text: str
    state: str
    done: bool = False
    order_summary: list[dict] | None = None
    text_en: str = ""
    text_zh: str = ""


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

    def greeting_zh(self) -> str:
        return self.restaurant.policy("ai_disclosure", "zh")

    def handle(self, utterance: str) -> Reply:
        self.lang = "zh" if has_cjk(utterance) else "en"
        context = Context(
            state=self.state,
            order_item_ids=[line.item.id for line in self.order.lines],
        )
        intents = self.backend.parse(utterance, context)
        parts: dict[str, list[str]] = {lang: [] for lang in LANGS}
        for intent in intents:
            reply = self._apply(intent)
            parts["en"].append(reply.text_en)
            parts["zh"].append(reply.text_zh)
            if reply.done or self.state == "HANDOFF":
                return self._join(parts, reply.done, reply.order_summary)
            if self.state == "READ_BACK" and context.state != "READ_BACK":
                # entered READ_BACK this turn: the caller has not heard the
                # read-back yet, so any further intents (e.g. a same-utterance
                # "confirm" from an LLM backend) must wait for their answer
                break
        return self._join(parts, False, None)

    def _join(self, parts: dict[str, list[str]], done: bool,
              order_summary: list[dict] | None) -> Reply:
        en = "\n".join(x for x in parts["en"] if x)
        zh = "\n".join(x for x in parts["zh"] if x)
        return Reply(en if self.lang == "en" else zh, self.state, done,
                     order_summary=order_summary, text_en=en, text_zh=zh)

    def _bi(self, key: str, **kw) -> tuple[str, str]:
        """Render a template in both languages. A kwarg may be a callable
        taking the language ("en"/"zh") for language-dependent pieces."""
        def resolve(lang: str) -> dict:
            return {k: (v(lang) if callable(v) else v) for k, v in kw.items()}
        return t("en", key, **resolve("en")), t("zh", key, **resolve("zh"))

    def _reply(self, texts: tuple[str, str], done: bool = False,
               order_summary: list[dict] | None = None) -> Reply:
        en, zh = texts
        return Reply(en if self.lang == "en" else zh, self.state, done,
                     order_summary=order_summary, text_en=en, text_zh=zh)

    def _size_options(self, item, lang: str) -> str:
        if lang == "zh":
            return "或".join(size_zh(s.name) for s in item.sizes)
        return " or ".join(s.name for s in item.sizes)

    def _handoff(self, msg_en: str, msg_zh: str) -> Reply:
        self.state = "HANDOFF"
        order_summary = self.order.summary() if self.order.lines else None
        if order_summary:
            msg_en += t("en", "saved_order_suffix")
            msg_zh += t("zh", "saved_order_suffix")
        return self._reply((msg_en, msg_zh), done=True, order_summary=order_summary)

    def _apply(self, intent: Intent) -> Reply:
        if intent.kind == "allergen":
            return self._handoff(self.restaurant.policy("allergen_policy", "en"),
                                 self.restaurant.policy("allergen_policy", "zh"))
        if intent.kind == "request_human":
            return self._handoff(t("en", "handoff_person"), t("zh", "handoff_person"))
        if intent.kind == "goodbye":
            if self.order.lines and self.state != "CONFIRMED":
                # never let a caller hang up believing an unplaced order exists
                self.state = "READ_BACK"
                return self._reply(self._bi(
                    "goodbye_unplaced",
                    read_back=lambda lang: self.order.read_back(lang)))
            return self._reply(self._bi("goodbye", name=self.restaurant.name),
                               done=True)
        if intent.kind == "faq":
            topic = intent.topic
            return self._reply((faq_mod.answer(topic, self.restaurant, "en"),
                                faq_mod.answer(topic, self.restaurant, "zh")))

        if intent.kind == "item_price":
            item = self.menu.find(intent.item_query)
            if not item:
                return self._reply(self._bi("price_unsure"))
            return self._reply((price_text(item, "en"), price_text(item, "zh")))

        if intent.kind == "add_item":
            item = self.menu.find(intent.item_query)
            if not item:
                return self._reply(self._bi("unknown_item", query=intent.item_query))
            if intent.size and item.sizes[0].name and not item.size_named(intent.size):
                return self._reply(self._bi(
                    "size_choice", name=item.display_name,
                    options=lambda lang: self._size_options(item, lang)))
            if intent.qty > 20:
                # an STT mis-hear shouldn't silently create a $7,000 order
                return self._reply(self._bi("qty_check", qty=intent.qty,
                                            name=item.display_name))
            line = self.order.add(item, qty=intent.qty,
                                  size_name=intent.size or None, notes=intent.notes)
            self.state = "ORDERING"
            return self._reply(self._bi("added", desc=line.describe))

        if intent.kind == "remove_item":
            item = self.menu.find(intent.item_query)
            line = self.order.find_line(item, intent.size or None) if item else None
            if not line:
                return self._reply(self._bi("not_on_order"))
            self.order.remove(line)
            self.state = "ORDERING" if self.order.lines else "OPEN"
            return self._reply(self._bi("removed", desc=line.describe))

        if intent.kind == "set_qty":
            line = None
            if intent.item_query:
                item = self.menu.find(intent.item_query)
                line = self.order.find_line(item, intent.size or None) if item else None
            elif self.order.lines:
                line = self.order.lines[-1]
            if not line:
                return self._reply(self._bi("which_change"))
            if intent.qty <= 0:
                self.order.remove(line)
                self.state = "ORDERING" if self.order.lines else "OPEN"
                return self._reply(self._bi("removed_name",
                                            name=line.item.display_name))
            line.qty = intent.qty
            self.state = "ORDERING"
            return self._reply(self._bi("okay", desc=line.describe))

        if intent.kind == "done_ordering":
            if not self.order.lines:
                return self._reply(self._bi("nothing_yet"))
            self.state = "READ_BACK"
            return self._reply(self._bi(
                "read_back_q", read_back=lambda lang: self.order.read_back(lang)))

        if intent.kind == "confirm" and self.state == "READ_BACK":
            self.state = "CONFIRMED"
            return self._reply(self._bi("confirmed",
                                        eta=self.restaurant.pickup_minutes,
                                        ticket=format_ticket(self.order)),
                               done=True)

        if intent.kind == "deny" and self.state == "READ_BACK":
            self.state = "ORDERING"
            return self._reply(self._bi("fix_what"))

        return self._reply(self._bi("fallback"))
