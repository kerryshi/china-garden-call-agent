# STATUS — china-garden call agent

**Where we are:** slice 1 (conversation core) in progress — scaffold + plan committed,
implementation underway. See PLAN.md for the slice design.

**In progress:** menu/order/faq/dialog/backends/ticket/cli implementation + tests.

**Next actions:**
- Finish slice 1 with evidence (pytest, ruff, CLI demo transcript) + independent review.
- Kerry: validate the missed-calls premise (call the restaurant at dinner rush).
- Kerry: real menu data — data/menu.json ships with a small starter menu; replace with the
  actual China Garden menu (family's call on items/prices).
- Slice 2 candidates: Haiku live hardening, CPU STT/TTS spike on the old PC, Asterisk/FXO.

**Open questions:**
- Old PC as dev+on-prem box: when to set it up?
- Kitchen ticket hand-off: printer at the restaurant, or screen for now?

**Last updated:** 2026-07-05 (autonomous session)
