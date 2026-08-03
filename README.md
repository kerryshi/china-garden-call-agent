# China Garden Call Agent

Inbound AI phone agent for China Garden (3207 S Holden Rd, Greensboro NC) — the family's
Chinese takeout restaurant. Scope: **FAQ + takeout order-taking with mandatory read-back**
(the top review complaint is order accuracy — read-back is the product story).

Architecture (decided 2026-07-01): hybrid — local voice (CPU STT/TTS) on an on-prem box with
FXO ingress, humans-first ring → AI rollover; the **brain is cloud Claude Haiku** behind a
swappable backend interface. This repo starts with the conversation core (text in → text out);
telephony and voice land later on the on-prem box.

Hard rules baked into the agent: disclose AI, keep payments off the call (PCI), hard-refuse
allergen safety questions (liability — hand off to a human), human fallback on request.

## Quickstart

```
python -m venv .venv
.venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m china_garden.cli          # interactive call simulation
.venv\Scripts\python -m china_garden.cli --script demo   # scripted demo conversation
```

## Demo webapp (in-person sales surface)

Call-style demo for pitching: the left panel is a phone call (ring → AI answers → hands-free
back-and-forth, timer, live caption, transcript drawer), the right panel is the restaurant's
view — live bilingual kitchen ticket, simulated SMS relay, protections that light up mid-call,
pricing/ROI. All page copy has an English/中文 toggle, **and the agent itself understands
Chinese**: a turn in 中文 is parsed and answered in 中文 (per-turn; English works as before).

```
.venv\Scripts\pip install -e .[web,tts]
bash scripts/fetch-tts.sh          # one-time ~340MB: Kokoro-82M voice (Apache-2.0)
.venv\Scripts\python -m uvicorn china_garden.web:app --port 8000
# open http://localhost:8000
```

Voice: English replies use the local Kokoro neural voice (offline, `/api/tts`); without the
model files the page falls back to the OS voice and says so in the badge. Chinese replies use
the OS Chinese voice. Voice input: 🎤 works when online in Chrome (cloud STT; toggle EN/中
for recognition language). Offline, use macOS dictation — press fn twice — or type.
To show the page on a phone without deploying: `cloudflared tunnel --url http://localhost:8000`.

**Understanding backend** (`CG_BACKEND`): `rule` (default — deterministic, offline, rigid),
`claude` (the real brain on the **Claude Max plan** — headless `claude -p` on the machine's
Claude Code login, no API key; ~8–12s/turn), or `haiku` (direct API, needs a key; fast lane).
Terminal run with the subscription brain:

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
