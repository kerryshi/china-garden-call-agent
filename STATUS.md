# STATUS — china-garden call agent

_Internal working log. Start at [README.md](README.md)._

**Round 7: pre-pitch QA + pricing locked** — 22-check live battery (safety
handoffs en+zh, PCI, session isolation, goodbye guard, corrections, TTS,
page JS/i18n/id integrity) found ONE real bug: done-phrase remainders
("make it two egg rolls, that's all") parsed as additions and inflated the
order 3→5; now routed correction-first (removal → set_qty → adds), two
failing-first regressions, 175 tests green on BOTH machines, Mac demo log
clean. Pricing per synthetic study + field playbook (separate repo):
site shows $129/mo flat + founding-$99 note; ?price= variants for pitch
laddering. Demo machine current at 999168b.

**Shipped 2026-08-03 (desktop, round 3): voice-bug fix + bilingual display +
Haiku wiring** — root cause of "voice sounds terrible": the greeting's zh tail
made /api/tts 400 and the page latched onto the system voice for the whole
call — Kokoro was never heard. Fixed: greeting split en/zh in data, /api/tts
strips CJK from mixed text (400 only when nothing English remains), client
only disables Kokoro on 503/transport errors. Every reply now carries BOTH
languages (reply_en/reply_zh; dialog renders both, state mutates once) and the
caption/transcript show them stacked. CG_BACKEND=haiku switches understanding
to cloud Claude Haiku with a credential probe that refuses loudly (badge shows
"brain: rules/Claude AI" + note). 158 tests green, ruff clean; smoke: loud
haiku fallback verified, full greeting through Kokoro 200/320KB.
**BLOCKED on Kerry:** Anthropic API key on desktop+Mac for the Haiku live
smoke (then `CG_BACKEND=haiku` in the LaunchAgent env).

**Round 6: latency tail tamed** — hot-standby CLI rotation (a successor
process is spawned + init-exchanged in the background; rotation/failure
promotes it between turns - boot never lands in a caller turn; _ensure_active
waits for a mid-boot standby instead of double-booting), standing
instructions sent once per process (per-turn prompt = state + utterance),
--strict-mcp-config on spawns, first-sentence TTS streaming, second spoken
acknowledgment at ~4.8s for upstream spikes, and CLI failures now logged
(were silently swallowed). Escalated turns: desktop avg 4.7s (was 7.2, most
3-4s), Mac steady-state ~3s; clean turns ~0.01s. Known: the FIRST escalation
within ~40s of a server (re)start can wait on the standby boot (~10-15s on
the Air) - give the LaunchAgent a minute after reboot before demoing.

**Round 5: hybrid brain + fully bilingual page** — CG_BACKEND=claude now
builds HybridBackend: RuleBackend answers instantly (0.00-0.03s measured);
only parses containing unknown escalate to the persistent Claude CLI (~4s,
masked by a delayed spoken acknowledgment that no longer fires if the answer
beat it). "a couple/few" added to number words (longest-match scan). The demo
page dropped the EN/中文 toggle: every string renders English with Chinese
subtext beneath (majority-Chinese audience). 173 tests green.

**Round 4: subscription brain LIVE** — `ClaudeCliBackend` parses via headless
`claude -p --model claude-haiku-4-5 --output-format json` on the box's Claude
Code login (no API key; plan usage). Shared intent builder with HaikuBackend;
parse failure degrades to unknown (never crashes a call); `CG_BACKEND=claude`;
loud fallback when the CLI is missing. Live-fired on desktop through the web
app: messy English, mid-order correction, colloquial zh (帮我再加一个左宗鸡，
要辣一点的) all parsed right; 8-12s/turn (CLI overhead - the API-key path is
the fast lane when a key lands). Mac LaunchAgent runs CG_BACKEND=claude.

**Shipped 2026-08-03 (desktop, round 2): Chinese + call-feel + neural voice** —
(1) the agent understands Simplified Chinese: CJK-aware menu matching (zh
names/aliases in menu.json), a zh RuleBackend path mirroring the safety-first
ordering (allergen/human first, zh numerals/measure words, 大/小 sizes,
removal-object resolution so 不要X never mis-removes), and bilingual reply
templates (`strings.py`; zh wording NEEDS Kerry/family review, incl.
restaurant.json `zh` policies + greeting tail); kitchen ticket now bilingual
("2 x Egg Roll  春卷"). (2) Demo page reworked to feel like a call: ring →
answer → hands-free loop, timer, caption, transcript drawer, EN/中 mic switch.
(3) English replies via local Kokoro-82M (`/api/tts`, `[tts]` extra,
`scripts/fetch-tts.sh`, Apache-2.0 — Fish/OpenAudio rejected: CC-BY-NC
weights); zh replies via OS voice; visible engine badge, 503→system-voice
fallback. 155 tests green (22 new, failing-first), ruff clean; live smoke:
full zh order over HTTP correct incl. ticket, TTS 96KB WAV in 0.6s.
(Earlier zh curl smoke failed from Windows shell mojibake — send UTF-8 JSON
via --data-binary @file, never inline CJK on the command line.)

**Shipped 2026-08-03 (desktop): demo webapp** — in-person sales surface at
`china_garden.web` (FastAPI, `[web]` extra) + `static/demo.html`: caller phone
UI (browser TTS via OS voices, tap-to-talk mic when online, offline = macOS
dictation/typing) beside the restaurant view (live kitchen ticket, simulated
SMS relay, protections lighting up mid-call, $99-149/mo pricing + ROI calc),
owner-side copy EN/中文 toggle (Kerry to review the Chinese before any demo).
133 tests green (6 new in `tests/test_web.py`, failing-first), ruff clean,
live uvicorn smoke: full order via curl incl. ticket/spoken-text split.
Demo machine = MacBook Air; run recipe in README. Product/telephony direction
now lives in the separate takeline repo; this repo stays
the family instance + demo.

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
**Mac leg — PROVEN 2026-07-19 (later the same day, Mac awake):** pushed master
(`7f149ed..70cec5b`), set `core.hooksPath=.githooks` on the Mac clone (hooks
arrived executable, venv there already had dev deps). Watched red-before-green
over ssh: planted failing test → commit REFUSED (`1 failed, 127 passed` then
"pre-commit REFUSED: test failures above. Commit blocked.", exit 1, HEAD
unmoved at `70cec5b`); cleaned; green `--allow-empty` commit passed the full
gate (`127 passed`, <1s) and was reset away. Both machines are now gated with
watched refusals; the gate travels by `git push mac master`.

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

**Last updated:** 2026-07-19 (pre-commit CI gate installed + refuse-proven on BOTH machines)
