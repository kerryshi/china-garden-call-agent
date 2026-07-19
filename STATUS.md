# STATUS — china-garden call agent

**Where we are:** slice 1 (conversation core) BUILT, reviewed, and hardened —
`eff81c9`, plus safety-lens hardening `8d8123c` (ingredient-question handoffs,
PCI phrasings, Haiku clamp). A full takeout call runs end-to-end in text: AI-disclosed greeting →
FAQ → multi-item order → mandatory read-back → confirm → kitchen ticket.
Deterministic RuleBackend is the default; HaikuBackend (claude-haiku-4-5,
forced tool use, strict schema) sits behind the same interface, live-untested
(no API credentials exercised on this box yet).

**Quality evidence:** 127 tests green (verified 2026-07-15; 36 are regressions
from an independent 3-lens review that drove ~50 adversarial probe
conversations — see `tests/test_review_regressions.py`), ruff clean, demo
transcript (`python -m china_garden.cli --script demo`) correct incl. tax math.
Review MUST-FIXes all applied: deny-vs-confirm ordering, 'and'-in-dish-name
double-adds, removal fallthrough, allergen coverage, bare-"no" mismatch,
goodbye losing unplaced orders.

**In progress:** nothing mid-flight; working tree clean.

**CI gate (2026-07-19, PRD WS4):** pre-commit hook at `.githooks/pre-commit`
runs `ruff check --no-cache .` + `python -m pytest -q` via the repo venv
(per-OS path from `.githooks/env.sh`: `.venv/Scripts/python.exe` on Windows,
`.venv/bin/python` on the Mac). Install per clone (hooks are repo content, the
config is not): `git config core.hooksPath .githooks`. Installed + proven on
the desktop: planted ruff red refused (exit 1, HEAD unmoved at `7f149ed`),
planted pytest red refused (1 failed/127 passed, exit 1, HEAD unmoved), green
commit `d87dc20` passed with the hook firing. Runtime ~1.8–3.2s measured vs
the 10s budget — no demotion needed. Stripped-env commit proof: see the commit
that added this paragraph. Refuse-over-skip: missing venv is a named refusal
with the create recipe (`python -m venv .venv && .venv/*/pip install -e ".[dev]"`).
`.gitattributes` pins LF on `.githooks/*` so the hooks run under `sh` on the Mac.
**Named holes (accepted):** `--no-verify` bypasses the gate; rebase/cherry-pick
run no hooks (rewritten commits land unchecked); a GUI-client (VS Code) commit
has not yet been exercised — named gap for Kerry.
**Mac leg — BLOCKED 2026-07-19 (Mac asleep/unreachable):** two ssh attempts
timed out (`ssh mac`, exit 255, "connect to host 100.102.79.63 port 22:
Connection timed out"). The hook + env.sh are committed on master and travel by
`git push mac master` once it wakes. Install recipe on the Mac (unproven there
until watched refusing):
1. From the desktop: `git push mac master`.
2. On the Mac: `cd ~/Projects/china-garden && git config core.hooksPath .githooks`.
3. If no `.venv` exists there: attempt a commit and watch the hook's NAMED
   missing-venv refusal — that observation IS the refuse-over-skip proof for
   the venv-less state. Green commits then need: `python3 -m venv .venv &&
   .venv/bin/pip install -e ".[dev]"`.
4. With a venv: plant a red (working-tree failing test), attempt a commit,
   watch the refusal with HEAD unmoved, clean up, then a green commit.
Until step 4 is recorded, the Mac clone is gated on paper only —
decoration-by-omission per the PRD, so this is a live TODO, not done.

**Next actions:**
- Kerry: validate the missed-calls premise (call the restaurant at dinner rush).
- Kerry: replace `data/menu.json` starter menu + confirm `data/restaurant.json`
  placeholders (hours, sales_tax_bps=675, pickup_minutes=15) — flagged in-file.
- Live-smoke the HaikuBackend once credentials are on this box
  (`pip install -e .[llm]`, then `python -m china_garden.cli --backend haiku`).
- Slice 2 candidates: CPU STT/TTS spike on the old PC, Asterisk/FXO, Haiku
  live hardening. (price-FAQ intent AND handoff briefing SHIPPED 2026-07-12,
  catering FAQ SHIPPED 2026-07-15 - see below.)

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

**Also shipped 2026-07-12 (the v2.1 harness's proof run):** handoff briefing —
`Reply` gains a caller-safe `order_summary` snapshot (item/qty/size/notes) and a
natural "order saved" line when a HANDOFF happens mid-order, so the telephony
layer can brief the human who picks up. Empty-order handoffs byte-identical to
before. 122 tests green (7 new, failing-first), ruff clean. Run record:
agentic-workflow/runs/2026-07-12_1811_add-a-handoff-briefing-to-the-china-garden-call/.

**Shipped 2026-07-15 (desktop, via the v2 harness — queue day):** catering /
large-order FAQ — family-confirmed decline: no catering service, but large
takeout orders welcome with advance notice; answers from `data/restaurant.json`
(no hardcoded policy text) via `faq.py` + `backends.py`. `47d7185`, 127 tests
green (5 new in `tests/test_catering_faq.py`), ruff clean. Run record:
agentic-workflow/runs/2026-07-15_1519_add-a-catering-large-order-faq-topic-to-the-chin/.

**Last updated:** 2026-07-19 (pre-commit CI gate installed + refuse-proven on desktop; Mac leg blocked, recipe above)
