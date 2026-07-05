import pytest

from china_garden.backends import Context, RuleBackend


@pytest.fixture
def backend(menu):
    return RuleBackend(menu)


def test_single_item(backend):
    intents = backend.parse("can I get an egg roll", Context())
    assert intents[0].kind == "add_item"
    assert intents[0].item_query == "Egg Roll"
    assert intents[0].qty == 1


def test_qty_digits_and_words(backend):
    assert backend.parse("3 egg rolls", Context())[0].qty == 3
    assert backend.parse("two egg rolls", Context())[0].qty == 2


def test_size_extraction(backend):
    intent = backend.parse("a quart of wonton soup", Context())[0]
    assert intent.kind == "add_item"
    assert intent.size == "quart"


def test_multi_item_with_and(backend):
    intents = backend.parse("two egg rolls and a quart of wonton soup", Context())
    assert [i.kind for i in intents] == ["add_item", "add_item"]
    assert intents[0].qty == 2
    assert intents[1].size == "quart"


def test_notes(backend):
    intent = backend.parse("one general tso extra spicy", Context())[0]
    assert intent.notes == "extra spicy"


def test_note_after_comma_attaches_to_previous_item(backend):
    # regression: "item, extra spicy" split the note into its own chunk and dropped it
    intents = backend.parse("one general tso's chicken, extra spicy", Context())
    assert len(intents) == 1
    assert intents[0].kind == "add_item"
    assert intents[0].notes == "extra spicy"


def test_allergen_always_wins(backend):
    intents = backend.parse("does the general tso have peanuts?", Context())
    assert intents[0].kind == "allergen"


def test_request_human(backend):
    assert backend.parse("let me talk to a person", Context())[0].kind == "request_human"


def test_faq_topics(backend):
    assert backend.parse("what time do you close", Context())[0].topic == "hours"
    assert backend.parse("do you deliver", Context())[0].topic == "delivery"
    assert backend.parse("can I pay with a card", Context())[0].topic == "payment"


def test_done_ordering(backend):
    assert backend.parse("that's it", Context(state="ORDERING"))[0].kind == "done_ordering"


def test_confirm_deny_only_in_read_back(backend):
    assert backend.parse("yes that's right", Context(state="READ_BACK"))[0].kind == "confirm"
    assert backend.parse("no that's wrong", Context(state="READ_BACK"))[0].kind == "deny"


def test_remove(backend):
    intent = backend.parse("remove the egg rolls", Context(state="ORDERING"))[0]
    assert intent.kind == "remove_item"
    assert intent.item_query == "Egg Roll"


def test_unknown(backend):
    assert backend.parse("flurble wurble", Context())[0].kind == "unknown"
