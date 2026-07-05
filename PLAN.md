# Plan — Slice 1: the conversation core (no voice, no telephony)

**Goal:** a takeout call, simulated as text turns, handled end-to-end: greet (with AI
disclosure) → answer FAQs → take an order → **read the full order back** → confirm → emit a
kitchen ticket. Deterministic core, LLM behind an interface. This is the piece every later
layer (STT/TTS, FXO/Asterisk) wraps; it must be testable without any of them.

**Why this slice first:** the settled architecture (2026-07-01) puts the brain in cloud Haiku
and voice on a CPU box — both are integration work around a conversation core that doesn't
exist yet. Order accuracy (read-back) is the product story; that logic is pure software and
fully verifiable today. The kitchen hand-off (ticket) was flagged "prototype early."

## Design

- `data/menu.json` + `data/restaurant.json` — offerings and facts are data, not code.
  Menu items: id, name, aliases, sizes/prices, options. Restaurant: hours, address, phone,
  payment, delivery policy, FAQ text.
- `menu.py` — load/validate menu; fuzzy item lookup (name + aliases, case/punct-insensitive).
- `order.py` — Order/OrderLine; add/remove/set-quantity; money as **integer cents**;
  NC prepared-food sales tax; `read_back()` renders the confirmation script.
- `faq.py` — keyword-matched answers from restaurant.json; **hard-refusal topics**
  (allergens → human handoff; payments → "pay at pickup, we never take card numbers by AI").
- `dialog.py` — turn state machine: GREET → OPEN (faq/order intents) → ORDERING →
  READ_BACK (mandatory before CONFIRMED) → CONFIRMED/HANDOFF. Every reply comes with the
  state so the caller (CLI now, telephony later) stays dumb.
- `backends.py` — `LLMBackend` protocol: `parse(utterance, context) -> Intent`.
  - `RuleBackend` — deterministic keyword/pattern parser; default; what tests use.
  - `HaikuBackend` — cloud Claude Haiku tool-calling parser (per claude-api docs);
    constructed only when explicitly selected AND an API key exists; never imported by tests.
- `ticket.py` — kitchen ticket: plain-text, printable-width, order lines + notes + totals.
- `cli.py` — `python -m china_garden.cli` interactive; `--script demo` runs a canned
  conversation and prints the transcript (the evidence surface).

## Non-goals (later slices)
Voice (STT/TTS), telephony (Asterisk/FXO), order persistence, POS/CMO integration,
Haiku live-call hardening, the branded Miso greeting.

## Validation
- pytest: order math (qty/sizes/tax/cents), read-back completeness (every line present),
  menu fuzzy lookup, FAQ hard-refusals, dialog happy path + human-handoff path.
- ruff clean. CLI `--script demo` transcript captured as evidence.
- Fresh independent review before ship (reviewer subagent).
