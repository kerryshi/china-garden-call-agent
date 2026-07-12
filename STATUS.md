# STATUS — china-garden call agent

**Where we are:** slice 1 (conversation core) BUILT, reviewed, and hardened —
`eff81c9`, plus safety-lens hardening `8d8123c` (ingredient-question handoffs,
PCI phrasings, Haiku clamp). A full takeout call runs end-to-end in text: AI-disclosed greeting →
FAQ → multi-item order → mandatory read-back → confirm → kitchen ticket.
Deterministic RuleBackend is the default; HaikuBackend (claude-haiku-4-5,
forced tool use, strict schema) sits behind the same interface, live-untested
(no API credentials exercised on this box yet).

**Quality evidence:** 77 tests green (36 are regressions from an independent
3-lens review that drove ~50 adversarial probe conversations — see
`tests/test_review_regressions.py`), ruff clean, demo transcript
(`python -m china_garden.cli --script demo`) correct incl. tax math.
Review MUST-FIXes all applied: deny-vs-confirm ordering, 'and'-in-dish-name
double-adds, removal fallthrough, allergen coverage, bare-"no" mismatch,
goodbye losing unplaced orders.

**In progress:** nothing mid-flight; working tree clean.

**Next actions:**
- Kerry: validate the missed-calls premise (call the restaurant at dinner rush).
- Kerry: replace `data/menu.json` starter menu + confirm `data/restaurant.json`
  placeholders (hours, sales_tax_bps=675, pickup_minutes=15) — flagged in-file.
- Live-smoke the HaikuBackend once credentials are on this box
  (`pip install -e .[llm]`, then `python -m china_garden.cli --backend haiku`).
- Slice 2 candidates: CPU STT/TTS spike on the old PC, Asterisk/FXO, Haiku
  live hardening, handoff briefing (HANDOFF replies don't carry the order-so-far
  for the human who picks up - the telephony layer will need it; safety-lens NIT).
  (price-FAQ intent SHIPPED 2026-07-12 - see below.)

**Open questions:**
- Old PC as dev+on-prem box: when to set it up?
- Kitchen ticket hand-off: printer at the restaurant, or screen for now?

**Shipped 2026-07-12 (Mac, via the v2 harness — its first real-size task):**
price-FAQ intent ("how much is X" / "what does X cost" / "cost of X") answers
from data/menu.json; multi-size items quote both sizes; multi-item questions
answer the first-mentioned item; unresolved price questions short-circuit to a
clarification and can NEVER place an order (two harness-review must-fix rounds
proved that fallthrough). 115 tests green (23 new in tests/test_price_faq.py,
all failing-first), ruff clean. Harness run record:
agentic-workflow/runs/2026-07-12_1617_add-a-price-faq-intent-to-the-china-garden-call/.

**Last updated:** 2026-07-12 (price-FAQ intent shipped through the harness on the Mac)
