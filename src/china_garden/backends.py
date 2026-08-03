"""Intent parsing behind a swappable backend.

RuleBackend is deterministic and is what tests (and the default CLI) use.
HaikuBackend calls cloud Claude Haiku via forced tool use; it is constructed
only when explicitly selected and requires the [llm] extra + credentials.
Tests must never depend on a live API call (AGENTS.md rule).

Parse priority is safety-first and state-aware (ordering matters — the
2026-07-05 review showed misordered checks confirm wrong orders):
  allergen > human > READ_BACK corrections > goodbye > FAQ > price > done > remove > set_qty > add
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .menu import Menu

KINDS = (
    "add_item", "remove_item", "set_qty", "done_ordering", "confirm", "deny",
    "faq", "item_price", "allergen", "request_human", "goodbye", "unknown",
)
FAQ_TOPICS = ("hours", "address", "phone", "delivery", "payment", "catering")

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_SIZE_WORDS = {"pint": "pint", "quart": "quart", "small": "pint", "large": "quart"}

# Safety first: false-positive handoffs are acceptable by policy; a missed
# allergen question is not. "sesame"/"egg" alone collide with menu items, so
# they only appear in unambiguous forms.
_ALLERGEN = (
    r"\b(allerg\w*|peanut\w*|nuts?|tree nut|gluten|celiac|dairy|milk|lactose|"
    r"shellfish|shrimp|fish|soy|msg|sesame oil|vegan|vegetarian|ingredients?)\b"
    r"|\bcontains?\b|\bwhat'?s in\b|\bwhat is in\b|\bsafe (to eat|for)\b"
    r"|\bcook\w* with\b|\bhave \w+ in (it|that)\b"
)
# a long digit run is someone reading a card number - refuse per PCI policy
_CARD_DIGITS = r"\d[\d\s\-]{11,}\d"
_HUMAN = r"\b(person|human|manager|operator|somebody|someone|staff)\b"
_AFFIRM = r"\b(yes|yeah|yep|correct|right|sounds good|perfect|sure)\b"
_NEGATE = r"\b(no|not|nope|wrong|isn'?t|actually)\b"
_REMOVAL = r"\b(remove|take\b.*\boff|cancel|no more|drop|scratch|get rid of)\b"
_REMOVAL_VERBS = r"\b(remove|take|off|cancel|no more|drop|scratch|get rid of)\b"
_DONE = (r"(that'?s (it|all)|thats (it|all)|that'?ll be (all|it)|nothing else|"
         r"i'?m done|all done|that'?s everything|thats everything)")
_PURE_CLOSE = r"^(no|nope|no thanks?|no thank you|nothing|done|all done|i'?m done)[\s.!]*$"
_QUESTION = (r"^(how|what|what'?s|why|when|where|who|do you|does|is|are|can you|"
             r"price|cost)\b")
_GOODBYE = r"\b(goodbye|bye)\b"
_SET_QTY = r"\b(?:make|change) (?:that|it)(?: to)?\s+(\w+)\b"
_STRIP = (r"\b(\d+|" + "|".join(_NUMBER_WORDS) + r"|" + "|".join(_SIZE_WORDS)
          + r"|of|the|please|also|add|i'?d like|i want|i'?ll (have|take)|"
          r"can i (get|have)|get|order|gimme|give me|extra \w+|no \w+|spicy|mild)\b")
# "how much is/are/does/do X" | "what(...) X cost" | "price/cost of/for X" -
# tried in order, each captures the item text into group 1
_PRICE_QUESTION_PATTERNS = (
    r"how much (?:is|are|does|do)\b\s*(.+)",
    r"what(?:'?s| is| are| does| do)?\b\s*(.+?)\s+cost\b",
    r"\b(?:price|cost)\b\s*(?:of|for)\s+(.+)",
)

# ---------------------------------------------------------------- Chinese (zh)
# Same safety-first ordering as English. False-positive handoffs are
# acceptable by policy; a missed allergen question is not. Bare 素 would
# collide with 素春卷, so only unambiguous forms appear.
_CJK_RE = re.compile(r"[一-鿿]")

_ZH_ALLERGEN = (r"过敏|忌口|花生|坚果|麸质|乳糖|海鲜|味精|素食|吃素|纯素|成分"
                r"|什么材料|有没有放|能不能吃")
_ZH_HUMAN = r"人工|真人|经理|客服|接线|找个人|找人说"
_ZH_AFFIRM = r"对|是的|没错|正确|好的|可以|行|嗯|确认"
_ZH_NEGATE = r"不对|不是|错了|有误"
_ZH_REMOVAL = r"不要|去掉|取消|删掉|别要|不用"
_ZH_DONE = r"就这样|就这些|没有了|不要别的|够了|可以下单|下单吧|好了"
_ZH_GOODBYE = r"再见|拜拜"
_ZH_PRICE = r"多少钱|什么价|价格|怎么卖"
_ZH_FAQ = (
    ("catering", r"酒席|宴席|大批|大单|聚会|派对|包办"),
    ("hours", r"几点|营业时间|开门|关门|营业到"),
    ("delivery", r"外卖|送餐|配送|送不送|送吗"),
    ("payment", r"付款|支付|刷卡|信用卡|现金|微信|支付宝"),
    ("address", r"地址|在哪|位置|怎么走"),
    ("phone", r"电话号码|号码是"),
)
_ZH_NOTES = r"特辣|加辣|多辣|微辣|不辣|少辣|少油|少盐|多饭|免葱"
_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9}
_ZH_MEASURES = "个份盒碗只例杯打"
_ZH_SIZES = (("大", "quart"), ("小", "pint"))
_ZH_CHUNK_SPLIT = r"，|,|、|；|。|还有|再来|再要|然后|跟|和"
_ZH_QTY = re.compile(rf"([0-9]+|[一两二三四五六七八九十]+)\s*[{_ZH_MEASURES}]?")
_ZH_STRIP = re.compile(
    rf"[0-9]+|[一两二三四五六七八九十]+[{_ZH_MEASURES}]|[{_ZH_MEASURES}]"
    r"|我要|我想要|想要|要|来|点|给我|帮我|加|请|谢谢|大的|小的|大|小|的|了|吧|呢|吗"
)


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _zh_num(token: str) -> int | None:
    """Chinese numerals up to 99 (一/两/二…十, 十X, X十, X十Y) or digits."""
    if token.isdigit():
        return int(token)
    if not token:
        return None
    if "十" in token:
        tens_s, _, units_s = token.partition("十")
        tens = _ZH_NUM.get(tens_s, 1) if tens_s else 1
        units = _ZH_NUM.get(units_s, 0) if units_s else 0
        return tens * 10 + units
    if len(token) == 1:
        return _ZH_NUM.get(token)
    return None


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
        # dish names/aliases containing " and " must not be split by the
        # conjunction chunker ("hot and sour soup" is one item, not two)
        phrases = set()
        for item in menu.items:
            for cand in (item.name, *item.aliases):
                if " and " in cand.lower():
                    phrases.add(cand.lower())
        self._and_phrases = sorted(phrases, key=len, reverse=True)

    def parse(self, utterance: str, context: Context) -> list[Intent]:
        text = utterance.lower().strip()
        if not text:
            return [Intent("unknown")]

        if has_cjk(text):
            return self._parse_zh(text, context)

        if re.search(_ALLERGEN, text):
            return [Intent("allergen")]
        if re.search(_HUMAN, text):
            return [Intent("request_human")]
        if re.search(_CARD_DIGITS, text):
            # caller is reading a card number - deliver the PCI refusal (and
            # still take any items in the same breath)
            return [Intent("faq", topic="payment"), *self._parse_items(text)]

        if context.state == "READ_BACK":
            return self._parse_read_back(text)

        if re.search(_GOODBYE, text):
            return [Intent("goodbye")]

        faq = self._match_faq(text)
        if faq:
            # an utterance can carry an order AND a question - keep both
            return [faq, *self._parse_items(text)]

        price = self._match_item_price(text)
        if price:
            # unlike FAQ, a price question's remainder is not a safe order
            # add - "how much are the egg rolls and crab rangoon" must not
            # silently add crab rangoon to the order (review finding)
            return [price]

        if context.state == "ORDERING" and re.match(_PURE_CLOSE, text):
            return [Intent("done_ordering")]

        done = re.search(_DONE, text)
        if done:
            remainder = text.replace(done.group(0), " ")
            return [*self._parse_items(remainder), Intent("done_ordering")]

        if re.search(_REMOVAL, text):
            return self._parse_removal(text)

        set_qty = self._parse_set_qty(text)
        if set_qty:
            return set_qty

        intents = self._parse_items(text)
        if intents:
            return intents
        return [Intent("unknown")]

    # ------------------------------------------------------------------ zh
    def _parse_zh(self, text: str, context: Context) -> list[Intent]:
        """Chinese path - mirrors the English safety-first ordering."""
        if re.search(_ZH_ALLERGEN, text):
            return [Intent("allergen")]
        if re.search(_ZH_HUMAN, text):
            return [Intent("request_human")]
        if re.search(_CARD_DIGITS, text):
            return [Intent("faq", topic="payment"), *self._parse_items_zh(text)]

        if context.state == "READ_BACK":
            return self._parse_read_back_zh(text)

        if re.search(_ZH_GOODBYE, text):
            return [Intent("goodbye")]

        for topic, pattern in _ZH_FAQ:
            if re.search(pattern, text):
                return [Intent("faq", topic=topic), *self._parse_items_zh(text)]

        if re.search(_ZH_PRICE, text):
            raw = re.sub(_ZH_PRICE, " ", text)
            cleaned = _ZH_STRIP.sub("", raw).strip(" ?？。！!")
            item = self.menu.find(cleaned) if cleaned else None
            # unresolved stays a price question - never falls through to an add
            return [Intent("item_price", item_query=item.name if item else cleaned)]

        done = re.search(_ZH_DONE, text)
        if done:
            remainder = text.replace(done.group(0), " ")
            return [*self._parse_items_zh(remainder), Intent("done_ordering")]

        if re.search(_ZH_REMOVAL, text):
            removal = self._parse_removal_zh(text)
            if removal:
                return removal
            # 不要X where X is not a menu item is a preference, not a removal -
            # fall through so it can attach as a note

        intents = self._parse_items_zh(text)
        if intents:
            return intents
        return [Intent("unknown")]

    def _parse_read_back_zh(self, text: str) -> list[Intent]:
        """Corrections outrank confirmation, exactly like the English path."""
        if re.search(_ZH_REMOVAL, text):
            removal = self._parse_removal_zh(text)
            if removal:
                return removal
        items = self._parse_items_zh(text)
        if re.search(_ZH_NEGATE, text):
            return [Intent("deny"), *items]
        if items:
            return items
        if re.search(_ZH_AFFIRM, text):
            return [Intent("confirm")]
        return [Intent("unknown")]

    def _parse_removal_zh(self, text: str) -> list[Intent] | None:
        stripped = re.sub(_ZH_REMOVAL, " ", text)
        size = ""
        for marker, canonical in _ZH_SIZES:
            if marker in stripped:
                size = canonical
                break
        cleaned = _ZH_STRIP.sub("", stripped).strip()
        item = self.menu.find(cleaned) if cleaned else None
        if not item:
            return None  # caller decides: note fall-through, never an add
        return [Intent("remove_item", item_query=item.name, size=size)]

    def _parse_items_zh(self, text: str) -> list[Intent]:
        intents: list[Intent] = []
        for chunk in re.split(_ZH_CHUNK_SPLIT, text):
            chunk = chunk.strip()
            if not chunk:
                continue
            qty = 1
            m = _ZH_QTY.search(chunk)
            if m:
                parsed = _zh_num(m.group(1))
                if parsed is not None:
                    qty = parsed
            qty = max(1, qty)
            size = ""
            for marker, canonical in _ZH_SIZES:
                if marker in chunk:
                    size = canonical
                    break
            notes = ""
            note_match = re.search(_ZH_NOTES, chunk)
            if note_match:
                notes = note_match.group(0)
            remainder = re.sub(_ZH_NOTES, "", chunk)
            cleaned = _ZH_STRIP.sub("", remainder).strip()
            item = self.menu.find(cleaned) if cleaned else None
            if item:
                intents.append(Intent("add_item", item_query=item.name, qty=qty,
                                      size=size, notes=notes))
                continue
            # a chunk that is only a preference (加辣 / 不要葱) belongs to the
            # item before the separator, not to a new intent
            if intents:
                extra = notes or (chunk if re.fullmatch(
                    r"(不要|少|多|免)[一-鿿]{1,3}", chunk) else "")
                if extra:
                    prev = intents[-1]
                    prev.notes = f"{prev.notes} {extra}".strip()
        return intents

    def _parse_read_back(self, text: str) -> list[Intent]:
        """Corrections outrank confirmation; confirm only without contradiction."""
        if re.search(_REMOVAL, text):
            return self._parse_removal(text)
        items = self._parse_items(text)
        if re.search(_NEGATE, text):
            return [Intent("deny"), *items]
        if items:
            return items  # additions reopen ORDERING; read-back reruns
        if re.search(_AFFIRM, text):
            return [Intent("confirm")]
        return [Intent("unknown")]

    def _match_faq(self, text: str) -> Intent | None:
        for topic, pattern in (
            ("catering", r"\b(cater\w*|large order|big order|bulk order|"
                         r"party (tray|order|platter)|feed a (crowd|party))\b"),
            ("hours", r"\b(hours?|open|close|closing|opening)\b"),
            ("delivery", r"\bdeliver\w*|door ?dash|grub ?hub\b"),
            ("payment", r"\b(pay|payment|card|credit|cash|apple pay|visa|"
                        r"mastercard|amex|discover|debit)\b"),
            ("address", r"\b(address|where are you|located|location)\b"),
            ("phone", r"\b(phone number|your number|what'?s the number)\b"),
        ):
            if re.search(pattern, text):
                return Intent("faq", topic=topic)
        return None

    def _match_item_price(self, text: str) -> Intent | None:
        matched = False
        best_raw = ""
        for pattern in _PRICE_QUESTION_PATTERNS:
            m = re.search(pattern, text)
            if not m:
                continue
            matched = True
            raw = re.sub(r"\bcost\b", " ", m.group(1)).strip(" ?.!")
            # chunk on 'and'/',' the way _parse_items does - resolving the
            # whole multi-item remainder as one query lets Menu.find's
            # tie-break answer a menu.json-earlier item instead of the one
            # the caller said first (review finding)
            for chunk in self._split_item_chunks(raw):
                cleaned = re.sub(_STRIP, " ", chunk).strip()
                if not cleaned:
                    continue
                item = self.menu.find(cleaned)
                if item:
                    return Intent("item_price", item_query=item.name)
            # keep trying later patterns before giving up - pattern 2 can
            # capture only filler ("what is THE cost of X" -> 'the') while
            # pattern 3 still holds the real item (review finding)
            cleaned_raw = re.sub(_STRIP, " ", raw).strip()
            if len(cleaned_raw) > len(best_raw):
                best_raw = cleaned_raw
        if matched:
            # still a price question even with no resolvable item - emit it
            # unresolved so parse() short-circuits into the dialog
            # clarification; falling through to _parse_items can place a
            # real order (review finding)
            return Intent("item_price", item_query=best_raw)
        return None

    def _parse_removal(self, text: str) -> list[Intent]:
        stripped = re.sub(_REMOVAL_VERBS, " ", text)
        stripped = re.sub(r"\b(the|of|my|from|order|please)\b", " ", stripped)
        item = self.menu.find(stripped.strip())
        if not item:
            # a removal request must NEVER fall through to an add
            return [Intent("unknown")]
        size = ""
        for word, canonical in _SIZE_WORDS.items():
            if re.search(rf"\b{word}\b", text):
                size = canonical
                break
        return [Intent("remove_item", item_query=item.name, size=size)]

    def _parse_set_qty(self, text: str) -> list[Intent] | None:
        m = re.search(_SET_QTY, text)
        if not m:
            return None
        word = m.group(1)
        qty = _NUMBER_WORDS.get(word) if not word.isdigit() else int(word)
        if qty is None:
            return None
        rest = text[m.end():].strip()
        item = self.menu.find(re.sub(_STRIP, " ", rest).strip()) if rest else None
        return [Intent("set_qty", item_query=item.name if item else "", qty=max(0, qty))]

    def _split_item_chunks(self, text: str) -> list[str]:
        """Split a multi-item utterance on 'and'/',' - dish names/aliases
        containing ' and ' are masked first so they stay whole."""
        masked = text
        for phrase in self._and_phrases:
            masked = masked.replace(phrase, phrase.replace(" and ", " & "))
        return [chunk.strip() for chunk in re.split(r"\band\b|,", masked) if chunk.strip()]

    def _parse_items(self, text: str) -> list[Intent]:
        intents: list[Intent] = []
        for chunk in self._split_item_chunks(text):
            if re.match(_QUESTION, chunk):
                continue  # "how much is X" / "do you have X" is not an order
            qty = 1
            digit = re.search(r"\b(\d+)\b", chunk)
            piece_count = re.search(r"\b\d+\s*(?:piece|pieces|pc|pcs)\b", chunk)
            if digit and not piece_count:
                qty = int(digit.group(1))
            elif not digit:
                for word, n in _NUMBER_WORDS.items():
                    if re.search(rf"\b{word}\b", chunk):
                        qty = n
                        break
            qty = max(1, qty)
            size = ""
            for word, canonical in _SIZE_WORDS.items():
                if re.search(rf"\b{word}\b", chunk):
                    size = canonical
                    break
            notes = ""
            note_match = re.search(r"\b(extra \w+|no \w+|spicy|mild)\b", chunk)
            # only suppress a note that IS a menu item verbatim - fuzzy
            # collisions ("no rice" ~ White Rice) must not eat the note
            if note_match and not self.menu.find_exact(note_match.group(1)):
                notes = note_match.group(1)
            item = self.menu.find(re.sub(_STRIP, " ", chunk).strip())
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
            "kind=request_human; a caller asking the price/cost of a menu item "
            "is kind=item_price with item_query set to that item, never a "
            "made-up price; in the READ_BACK state a plain agreement is "
            "kind=confirm and a correction is kind=deny - never confirm an "
            "utterance that also asks for a change."
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
                "content": (
                    f"Dialog state: {context.state}\n"
                    f"Order so far: {', '.join(context.order_item_ids) or 'empty'}\n"
                    f"Caller said: {utterance}"
                ),
            }],
        )
        for block in response.content:
            if block.type == "tool_use":
                raw = block.input.get("intents", [])
                intents = [
                    Intent(
                        kind=i.get("kind", "unknown"),
                        item_query=i.get("item_query", ""),
                        # set_qty may legitimately be 0 (= remove the line)
                        qty=max(0 if i.get("kind") == "set_qty" else 1,
                                int(i.get("qty", 1))),
                        size=i.get("size", ""),
                        notes=i.get("notes", ""),
                        topic=i.get("topic", ""),
                    )
                    for i in raw
                ]
                return intents or [Intent("unknown")]
        return [Intent("unknown")]
