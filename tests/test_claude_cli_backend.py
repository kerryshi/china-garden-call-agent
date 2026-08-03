"""ClaudeCliBackend: subscription-CLI parsing with an injected runner.

Tests never spawn the real CLI (AGENTS.md: no live API calls in tests).
"""

import json

import pytest

from china_garden.backends import ClaudeCliBackend, Context


def backend_with(menu, reply):
    return ClaudeCliBackend(menu, runner=lambda prompt: reply)


def test_parses_intents_from_json_reply(menu):
    reply = json.dumps({"intents": [
        {"kind": "add_item", "item_query": "Egg Roll", "qty": 2,
         "size": "", "notes": "", "topic": ""},
        {"kind": "faq", "item_query": "", "qty": 1, "size": "",
         "notes": "", "topic": "delivery"},
    ]})
    intents = backend_with(menu, reply).parse("two egg rolls, do you deliver?",
                                              Context())
    assert [(i.kind, i.item_query, i.qty) for i in intents] == [
        ("add_item", "Egg Roll", 2), ("faq", "", 1)]
    assert intents[1].topic == "delivery"


def test_fenced_json_reply(menu):
    reply = ('Here you go:\n```json\n{"intents": [{"kind": "request_human", '
             '"item_query": "", "qty": 1, "size": "", "notes": "", "topic": ""}]}\n```')
    intents = backend_with(menu, reply).parse("get me a person", Context())
    assert intents[0].kind == "request_human"


def test_garbage_reply_degrades_to_unknown(menu):
    intents = backend_with(menu, "sorry, I can't help with that").parse(
        "hi", Context())
    assert [i.kind for i in intents] == ["unknown"]


def test_runner_exception_degrades_to_unknown(menu):
    def boom(prompt):
        raise TimeoutError("cli timed out")
    intents = ClaudeCliBackend(menu, runner=boom).parse("hi", Context())
    assert [i.kind for i in intents] == ["unknown"]


def test_prompt_carries_menu_and_state(menu):
    seen = {}
    def capture(prompt):
        seen["prompt"] = prompt
        return json.dumps({"intents": []})
    ClaudeCliBackend(menu, runner=capture).parse(
        "hello", Context(state="READ_BACK", order_item_ids=["egg_roll"]))
    assert "Egg Roll / 春卷" in seen["prompt"]
    assert "Dialog state: READ_BACK" in seen["prompt"]
    assert "egg_roll" in seen["prompt"]


def test_empty_intents_is_unknown(menu):
    intents = backend_with(menu, '{"intents": []}').parse("hm", Context())
    assert [i.kind for i in intents] == ["unknown"]


@pytest.mark.parametrize("bad", ["{not json", "[]", ""])
def test_malformed_json_is_unknown(menu, bad):
    intents = backend_with(menu, bad).parse("hi", Context())
    assert [i.kind for i in intents] == ["unknown"]
