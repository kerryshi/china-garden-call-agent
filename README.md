# China Garden Call Agent

[![CI](https://github.com/kerryshi/china-garden-call-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/kerryshi/china-garden-call-agent/actions/workflows/ci.yml)

A bilingual (English/中文) AI phone agent that takes takeout orders for my family's Chinese
restaurant. In its hybrid mode, rules parse the clean turns instantly and Claude Haiku parses
the rest. On every backend a state machine, not the model, enforces the order read-back, so
no order is confirmed without one.

- **Hard rules, enforced in code:** discloses that it is an AI, keeps payment off the call (PCI),
  hands every allergen question to a human, and transfers to a person on request.
- **Tested adversarially:** 175 pytest tests, including safety regressions written failing-first
  after adversarial tests caught an order being confirmed on "no, that's not right"
  (`tests/test_review_regressions.py`, `tests/test_safety_regressions.py`).
- **Status:** conversation core and browser demo built and running end-to-end in text and voice;
  it has not taken a live phone call yet.

China Garden (3207 S Holden Rd, Greensboro NC) is the family's takeout restaurant. Scope:
**FAQ + takeout order-taking with mandatory read-back**; the top review complaint is order
accuracy, so read-back is the product story.

Architecture (decided 2026-07-01): hybrid — local voice (CPU STT/TTS) on an on-prem box with
FXO ingress, humans-first ring → AI rollover; the **brain is cloud Claude Haiku** behind a
swappable backend interface. This repo starts with the conversation core (text in → text out);
telephony and voice land later on the on-prem box.

## Quickstart

```
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q
python -m china_garden.cli                  # interactive call simulation
python -m china_garden.cli --script demo    # scripted demo conversation
```

## Demo webapp (in-person sales surface)

Call-style demo for pitching: the left panel is a phone call (ring → AI answers → hands-free
back-and-forth, timer, live caption, transcript drawer), the right panel is the restaurant's
view — live bilingual kitchen ticket, simulated SMS relay, protections that light up mid-call,
pricing/ROI. All page copy has an English/中文 toggle, **and the agent itself understands
Chinese**: a turn in 中文 is parsed and answered in 中文 (per-turn; English works as before).

```
pip install -e ".[web,tts]"
bash scripts/fetch-tts.sh          # one-time ~340MB: Kokoro-82M voice (Apache-2.0)
python -m uvicorn china_garden.web:app --port 8000
# open http://localhost:8000
```

Voice: English replies use the local Kokoro neural voice (offline, `/api/tts`); without the
model files the page falls back to the OS voice and says so in the badge. Chinese replies use
the OS Chinese voice. Voice input: 🎤 works when online in Chrome (cloud STT; toggle EN/中
for recognition language). Offline, use macOS dictation — press fn twice — or type.
To show the page on a phone without deploying: `cloudflared tunnel --url http://localhost:8000`.

**Understanding backend** (`CG_BACKEND`): `rule` (default — deterministic, offline, rigid),
`claude` (hybrid: rules first, unparsed turns go to Claude Haiku through the local Claude Code
CLI, `claude -p`; a dev/demo convenience that reuses the machine's login, ~8–12s on an escalated
turn), or `haiku` (Claude Haiku via the Anthropic API, needs a key; the deployment path).
Terminal run with the hybrid backend:

```
CG_BACKEND=claude .venv/bin/python -m uvicorn china_garden.web:app --port 8000
```

The badge under the avatar always shows which brain and voice are live; a missing CLI or
credentials degrades loudly to rules, never silently. Read-back/allergen/PCI guarantees are
enforced by the state machine on every backend.

## Layout

- `src/china_garden/` — package (menu, faq, order, dialog, backends, ticket, cli, web)
- `static/` — the demo webapp page (self-contained, offline-capable)
- `data/` — menu + restaurant info (edit these, not code, to change offerings)
- `tests/` — pytest suite
