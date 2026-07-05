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

## Layout

- `src/china_garden/` — package (menu, faq, order, dialog, backends, ticket, cli)
- `data/` — menu + restaurant info (edit these, not code, to change offerings)
- `tests/` — pytest suite
