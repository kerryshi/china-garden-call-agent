"""Demo webapp: the in-person sales surface for the China Garden call agent.

A thin HTTP layer over DialogSession - no dialog logic lives here. Serves the
split-view demo page (caller phone UI on the left, restaurant-side panels on
the right) plus the small JSON API the page drives. Fully offline with the
default rule backend; set CG_BACKEND=haiku (plus Anthropic credentials) to
run understanding through cloud Claude Haiku - the money/safety state machine
stays deterministic either way.

Run:  .venv/Scripts/python.exe -m uvicorn china_garden.web:app --port 8000
"""

from __future__ import annotations

import os
import re
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .backends import RuleBackend, has_cjk
from .dialog import DialogSession
from .faq import Restaurant
from .menu import Menu
from .ticket import WIDTH, format_ticket
from .tts import KokoroEngine

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
MAX_SESSIONS = 200
_TICKET_RULE = "=" * WIDTH


class ChatRequest(BaseModel):
    session_id: str
    utterance: str


class TTSRequest(BaseModel):
    text: str


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


_CJK_STRIP = re.compile(r"[一-鿿][一-鿿。！？，、“”‘’——]*")


def _english_only(text: str) -> str:
    """Drop CJK segments so mixed text can still go through the en voice."""
    return re.sub(r"\s{2,}", " ", _CJK_STRIP.sub(" ", text)).strip()


def create_app(tts: object = "auto", backend: str | None = None) -> FastAPI:
    """tts: "auto" loads Kokoro lazily if installed; None disables (503);
    anything else is used as the engine (tests inject a fake).
    backend: "rule" (default) or "haiku"; None reads CG_BACKEND."""
    menu = Menu.load()
    restaurant = Restaurant.load()
    sessions: OrderedDict[str, DialogSession] = OrderedDict()
    tts_state = {"engine": None if tts in ("auto", None) else tts,
                 "tried": tts != "auto"}
    app = FastAPI(title="China Garden call agent demo")

    requested = (backend or os.environ.get("CG_BACKEND", "rule")).lower()
    backend_name, backend_note = "rule", ""
    make_backend = lambda: RuleBackend(menu)  # noqa: E731
    if requested in ("claude", "claude-cli", "sub", "hybrid"):
        try:
            from .backends import ClaudeCliBackend, HybridBackend
            probe = HybridBackend(RuleBackend(menu),
                                  ClaudeCliBackend(menu))  # raises w/o the CLI
            probe.warm()  # spawn the persistent CLI before the first caller
            backend_name = "hybrid"
            make_backend = lambda: probe  # noqa: E731  (stateless per call)
        except Exception as e:  # visible degradation, never silent
            backend_note = f"claude CLI unavailable ({e}); using rules"
    elif requested == "haiku":
        try:
            from .backends import HaikuBackend
            probe = HaikuBackend(menu)  # raises without the [llm] extra
            # the SDK can construct credential-less and fail only at request
            # time - refuse now instead of 500ing mid-call
            if not (getattr(probe.client, "api_key", None)
                    or getattr(probe.client, "auth_token", None)):
                raise RuntimeError("no Anthropic credentials on this machine")
            backend_name = "haiku"
            make_backend = lambda: probe  # noqa: E731  (client is stateless)
        except Exception as e:  # visible degradation, never silent
            backend_note = f"haiku unavailable ({e.__class__.__name__}: {e}); using rules"

    def _tts_engine():
        if not tts_state["tried"]:
            tts_state["tried"] = True
            tts_state["engine"] = KokoroEngine.try_load()
        return tts_state["engine"]

    @app.post("/api/session")
    def create_session() -> dict:
        session = DialogSession(menu, restaurant, make_backend())
        session_id = uuid.uuid4().hex
        sessions[session_id] = session
        while len(sessions) > MAX_SESSIONS:
            sessions.popitem(last=False)
        return {
            "session_id": session_id,
            "greeting": session.greeting(),
            "greeting_zh": session.greeting_zh(),
            "backend": backend_name,
            "backend_note": backend_note,
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
            "reply_en": _spoken_text(reply.text_en),
            "reply_zh": _spoken_text(reply.text_zh),
            "lang": session.lang,
            "state": session.state,
            "done": reply.done,
            "handoff": session.state == "HANDOFF",
            "ticket": format_ticket(session.order) if confirmed else None,
            **_order_payload(session),
        }

    @app.get("/api/tts/status")
    def tts_status() -> dict:
        return {"available": _tts_engine() is not None, "engine": "kokoro"}

    @app.post("/api/tts")
    def tts_synthesize(req: TTSRequest) -> Response:
        engine = _tts_engine()
        if engine is None:
            raise HTTPException(status_code=503, detail="tts model not installed")
        # mixed text is fine - drop CJK segments (zh is spoken client-side);
        # only a text with no English left is an error
        text = _english_only(req.text) if has_cjk(req.text) else req.text
        if not text:
            raise HTTPException(status_code=400, detail="no English text to speak")
        return Response(content=engine.synthesize(text), media_type="audio/wav")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "demo.html")

    return app


app = create_app()
