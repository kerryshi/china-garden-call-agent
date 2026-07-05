# AGENTS.md

## Project Overview
Inbound AI call agent for China Garden, the owner's family Chinese-takeout restaurant
(Greensboro NC). Answers FAQ (hours, address, delivery, payment) and takes takeout orders
with a **mandatory read-back** before confirming. Real deployment target: an on-prem box at
the restaurant (FXO line, humans-first ring → AI rollover); brain = cloud Claude Haiku.
This repo currently implements the text conversation core; voice/telephony come later.

## Repository Structure
- `src/china_garden/` — package code (src layout)
- `data/` — menu.json + restaurant.json: all offerings/facts live in data, not code
- `tests/` — pytest suite

## Setup & Commands
- Install: `python -m venv .venv && .venv\Scripts\pip install -e .[dev]`
- Test: `.venv\Scripts\python -m pytest -q`
- Lint: `.venv\Scripts\ruff check --no-cache .`
- Run: `.venv\Scripts\python -m china_garden.cli` (add `--script demo` for the scripted demo)

## Coding Rules
- Reuse existing components/utilities before creating new ones.
- Keep changes minimal and scoped to the task. No unrelated refactors.
- Do not change public API behavior unless asked. Do not delete tests to make CI pass.
- Menu/restaurant facts belong in `data/`, never hardcoded in logic.
- The LLM sits behind `backends.LLMBackend`; tests use the deterministic `RuleBackend` —
  never make tests depend on a live API call.

## Validation Rules (evidence before "done")
- Dialog changes: paste a CLI transcript (scripted run) showing the flow.
- Order-math changes: before/after totals on a sample order.
- Always: run lint + relevant tests and report commands + results.

## Escalation (ask the human first)
- Anything customer-facing going LIVE (deployment, telephony hookup, greetings wording).
- Menu contents and prices (family's call), payment handling, allergen policy changes.
- Architecture, paid services, data deletion.

## Known Agent Mistakes
- (append here as they happen so future runs avoid them)
