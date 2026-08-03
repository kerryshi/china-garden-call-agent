"""FAQ answers from restaurant.json, plus the hard-refusal topics.

Hard rules (legal/safety, decided 2026-07-01): allergen questions are never
answered by the AI - always a human handoff. Payments never happen on the call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


_DAY_ZH = {"monday": "周一", "tuesday": "周二", "wednesday": "周三",
           "thursday": "周四", "friday": "周五", "saturday": "周六",
           "sunday": "周日"}


@dataclass(frozen=True)
class Restaurant:
    name: str
    address: str
    phone: str
    hours: dict[str, str]
    sales_tax_bps: int
    pickup_minutes: int
    payment_policy: str
    delivery_policy: str
    allergen_policy: str
    ai_disclosure: str
    catering: str | None = None
    zh: dict[str, str] | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> Restaurant:
        raw = json.loads((path or DATA_DIR / "restaurant.json").read_text(encoding="utf-8"))
        hours = {k: v for k, v in raw["hours"].items() if not k.startswith("_")}
        zh = {k: v for k, v in raw.get("zh", {}).items() if not k.startswith("_")}
        return cls(
            name=raw["name"],
            address=raw["address"],
            phone=raw["phone"],
            hours=hours,
            sales_tax_bps=raw["sales_tax_bps"],
            pickup_minutes=raw["pickup_minutes"],
            payment_policy=raw["payment_policy"],
            delivery_policy=raw["delivery_policy"],
            allergen_policy=raw["allergen_policy"],
            ai_disclosure=raw["ai_disclosure"],
            catering=raw.get("catering"),
            zh=zh,
        )

    def policy(self, key: str, lang: str = "en") -> str:
        """A policy string in the requested language, English fallback."""
        english = getattr(self, key) or ""
        if lang == "zh" and self.zh:
            return self.zh.get(key, english)
        return english


def answer(topic: str, r: Restaurant, lang: str = "en") -> str:
    """Answer a FAQ topic from data. Unknown topics get a safe fallback."""
    if lang == "zh":
        if topic == "hours":
            days = "\n".join(f"  {_DAY_ZH.get(day, day)}: {span}"
                             for day, span in r.hours.items())
            return f"我们的营业时间：\n{days}"
        if topic == "address":
            return f"我们的地址是 {r.address}。"
        if topic == "phone":
            return f"本机号码是 {r.phone}。"
        if topic == "delivery":
            return r.policy("delivery_policy", "zh")
        if topic == "payment":
            return r.policy("payment_policy", "zh")
        if topic == "catering" and r.catering:
            return r.policy("catering", "zh")
        return "这个我不太确定——说“人工”我帮您转真人。"
    if topic == "hours":
        days = "\n".join(f"  {day.capitalize()}: {span}" for day, span in r.hours.items())
        return f"Our hours are:\n{days}"
    if topic == "address":
        return f"We're at {r.address}."
    if topic == "phone":
        return f"This number is {r.phone}."
    if topic == "delivery":
        return r.delivery_policy
    if topic == "payment":
        return r.payment_policy
    if topic == "catering" and r.catering:
        return r.catering
    return "I'm not sure about that one - say 'person' and I'll get someone who knows."
