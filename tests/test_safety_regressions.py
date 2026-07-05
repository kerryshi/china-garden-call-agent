"""Regressions from the safety lens (re-run 2026-07-05 on eff81c9)."""

import pytest

from china_garden.backends import Context, HaikuBackend, RuleBackend

# --- ingredient questions without trigger keywords must still hand off -------

@pytest.mark.parametrize("utterance", [
    "tell me what's in the lo mein",   # was: added a lo mein to the order
    "what's in the crab rangoon",
    "what ingredients are in the lo mein",
    "is the rangoon safe for my kid",
    "does the egg roll have egg in it",
    "do you cook with fish sauce",
])
def test_ingredient_questions_hand_off(session, utterance):
    reply = session.handle(utterance)
    assert session.state == "HANDOFF"
    assert reply.done
    assert session.order.lines == []


# --- PCI refusal must fire on card brands and card-number digit runs ---------

@pytest.mark.parametrize("utterance", [
    "here's my visa, 4111 1111 1111 1111",
    "can i give you my mastercard number",
    "i want to give you my debit number",
])
def test_card_phrasings_get_pci_refusal(session, utterance):
    reply = session.handle(utterance)
    assert "never take card numbers" in reply.text


def test_card_number_with_order_keeps_items_and_refuses(session):
    reply = session.handle("two egg rolls and my visa is 4111 1111 1111 1111")
    assert "never take card numbers" in reply.text
    assert [(line.item.id, line.qty) for line in session.order.lines] == [("egg_roll", 2)]


# --- absurd quantities get a sanity check -------------------------------------

def test_huge_qty_asks_instead_of_adding(session):
    reply = session.handle("can i get 4111 egg rolls")
    assert session.order.lines == []
    assert "4111" in reply.text  # clarification, not 'Got it'


# --- HaikuBackend unit coverage via a fake client (no anthropic import) -------

class _FakeBlock:
    type = "tool_use"

    def __init__(self, intents):
        self.input = {"intents": intents}


class _FakeResponse:
    def __init__(self, intents):
        self.content = [_FakeBlock(intents)]


class _FakeMessages:
    def __init__(self, intents):
        self._intents = intents
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._intents)


class _FakeClient:
    def __init__(self, intents):
        self.messages = _FakeMessages(intents)


def _intent(**overrides):
    base = {"kind": "add_item", "item_query": "", "qty": 1, "size": "",
            "notes": "", "topic": ""}
    base.update(overrides)
    return base


def test_haiku_set_qty_zero_survives_clamp(menu):
    backend = HaikuBackend(menu, client=_FakeClient(
        [_intent(kind="set_qty", item_query="Egg Roll", qty=0)]))
    parsed = backend.parse("actually no egg rolls", Context(state="ORDERING"))
    assert parsed[0].kind == "set_qty"
    assert parsed[0].qty == 0  # was: clamped to 1, removal misfired


def test_haiku_add_item_qty_still_clamped_to_one(menu):
    backend = HaikuBackend(menu, client=_FakeClient(
        [_intent(kind="add_item", item_query="Egg Roll", qty=0)]))
    assert backend.parse("an egg roll", Context())[0].qty == 1


def test_haiku_request_shape_and_order_context(menu):
    client = _FakeClient([_intent(kind="confirm")])
    backend = HaikuBackend(menu, client=client)
    backend.parse("yes", Context(state="READ_BACK", order_item_ids=["egg_roll"]))
    kwargs = client.messages.last_kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_intents"}
    assert kwargs["tools"][0]["strict"] is True
    user_msg = kwargs["messages"][0]["content"]
    assert "READ_BACK" in user_msg
    assert "egg_roll" in user_msg  # was: model never saw the order contents


def test_rule_backend_set_qty_zero_still_works(menu):
    intents = RuleBackend(menu).parse("make that 0 egg rolls",
                                      Context(state="ORDERING"))
    assert intents[0].kind == "set_qty"
    assert intents[0].qty == 0
