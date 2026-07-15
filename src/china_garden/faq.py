"""FAQ answers from restaurant.json, plus the hard-refusal topics.

Hard rules (legal/safety, decided 2026-07-01): allergen questions are never
answered by the AI - always a human handoff. Payments never happen on the call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


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

    @classmethod
    def load(cls, path: Path | None = None) -> Restaurant:
        raw = json.loads((path or DATA_DIR / "restaurant.json").read_text(encoding="utf-8"))
        hours = {k: v for k, v in raw["hours"].items() if not k.startswith("_")}
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
        )


def answer(topic: str, r: Restaurant) -> str:
    """Answer a FAQ topic from data. Unknown topics get a safe fallback."""
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
