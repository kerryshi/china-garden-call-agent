"""Demo webapp: the in-person sales surface for the China Garden call agent.

A thin HTTP layer over DialogSession - no dialog logic lives here. Serves the
split-view demo page (caller phone UI on the left, restaurant-side panels on
the right) plus the small JSON API the page drives. Everything is local and
offline-capable: no external assets, no cloud calls (RuleBackend only).

Run:  .venv/Scripts/python.exe -m uvicorn china_garden.web:app --port 8000
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .backends import RuleBackend
from .dialog import DialogSession
from .faq import Restaurant
from .menu import Menu
from .ticket import WIDTH, format_ticket

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
MAX_SESSIONS = 200
_TICKET_RULE = "=" * WIDTH


class ChatRequest(BaseModel):
    session_id: str
    utterance: str


def _order_payload(session: DialogSession) -> dict:
    order = session.order
    return {
        "order": [
            {
                "item": line.item.name,
                "qty": line.qty,
                "size": line.size.name,
                "notes": line.notes,
                "line_total_cents": line.line_total_cents,
            }
            for line in order.lines
        ],
        "totals": {
            "subtotal_cents": order.subtotal_cents,
            "tax_cents": order.tax_cents,
            "total_cents": order.total_cents,
        },
    }


def _spoken_text(text: str) -> str:
    """Strip the ticket art out of a reply so TTS never reads it aloud."""
    return text.split(_TICKET_RULE)[0].rstrip()


def create_app() -> FastAPI:
    menu = Menu.load()
    restaurant = Restaurant.load()
    sessions: OrderedDict[str, DialogSession] = OrderedDict()
    app = FastAPI(title="China Garden call agent demo")

    @app.post("/api/session")
    def create_session() -> dict:
        session = DialogSession(menu, restaurant, RuleBackend(menu))
        session_id = uuid.uuid4().hex
        sessions[session_id] = session
        while len(sessions) > MAX_SESSIONS:
            sessions.popitem(last=False)
        return {
            "session_id": session_id,
            "greeting": session.greeting(),
            "restaurant": {
                "name": restaurant.name,
                "address": restaurant.address,
                "phone": restaurant.phone,
                "pickup_minutes": restaurant.pickup_minutes,
            },
        }

    @app.post("/api/chat")
    def chat(req: ChatRequest) -> dict:
        session = sessions.get(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")
        reply = session.handle(req.utterance)
        confirmed = session.state == "CONFIRMED"
        return {
            "reply": _spoken_text(reply.text),
            "state": session.state,
            "done": reply.done,
            "handoff": session.state == "HANDOFF",
            "ticket": format_ticket(session.order) if confirmed else None,
            **_order_payload(session),
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "demo.html")

    return app


app = create_app()
