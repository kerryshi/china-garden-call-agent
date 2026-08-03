"""HybridBackend: rules answer instantly; Claude only sees the messy turns."""

import json

from china_garden.backends import (
    ClaudeCliBackend,
    Context,
    HybridBackend,
    RuleBackend,
)


class CountingRunner:
    def __init__(self, reply):
        self.calls = 0
        self.reply = reply

    def __call__(self, prompt):
        self.calls += 1
        return self.reply


def hybrid_with(menu, cli_reply='{"intents": []}'):
    runner = CountingRunner(cli_reply)
    backend = HybridBackend(RuleBackend(menu), ClaudeCliBackend(menu, runner=runner))
    return backend, runner


def test_clean_turn_never_touches_claude(menu):
    backend, runner = hybrid_with(menu)
    intents = backend.parse("two egg rolls please", Context())
    assert intents[0].kind == "add_item" and intents[0].qty == 2
    assert runner.calls == 0


def test_zh_clean_turn_never_touches_claude(menu):
    backend, runner = hybrid_with(menu)
    intents = backend.parse("来两份春卷", Context())
    assert intents[0].kind == "add_item"
    assert runner.calls == 0


def test_couple_parses_as_two_in_rules(menu):
    backend, runner = hybrid_with(menu)
    intents = backend.parse("can i get a couple of egg rolls", Context())
    assert intents[0].qty == 2
    assert runner.calls == 0


def test_messy_turn_escalates_to_claude(menu):
    reply = json.dumps({"intents": [
        {"kind": "add_item", "item_query": "Hot and Sour Soup", "qty": 1,
         "size": "pint", "notes": "", "topic": ""}]})
    backend, runner = hybrid_with(menu, reply)
    intents = backend.parse("that sour soup thing my wife likes", Context())
    assert runner.calls == 1
    assert intents[0].item_query == "Hot and Sour Soup"


def test_claude_failure_still_degrades_to_unknown(menu):
    backend, runner = hybrid_with(menu, "not json at all")
    intents = backend.parse("blorp zorp", Context())
    assert runner.calls == 1
    assert [i.kind for i in intents] == ["unknown"]
