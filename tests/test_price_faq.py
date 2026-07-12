"""Price-FAQ intent: 'how much is X' / 'what does X cost' get X's price from
data/menu.json - never invented, never blocking the order/read-back flow."""

import pytest

from china_garden.backends import Context, Intent, RuleBackend


@pytest.fixture
def backend(menu):
    return RuleBackend(menu)


# --- backend: pattern + item resolution -------------------------------------

def test_how_much_is_single_size_item(backend):
    intent = backend.parse("how much is General Tso's Chicken", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "General Tso's Chicken"


def test_what_does_it_cost_alias_phrasing(backend):
    intent = backend.parse("what does the egg roll cost", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "Egg Roll"


def test_price_of_phrasing(backend):
    intent = backend.parse("what is the price of the crab rangoon", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "Crab Rangoon (6)"


def test_what_is_the_cost_of_phrasing(backend):
    # review finding: pattern 2's non-greedy capture stops at the first
    # ' cost' boundary (group='the'), and an unconditional unresolved return
    # there starved pattern 3 ('cost of X') of ever seeing the utterance
    intent = backend.parse("what is the cost of the egg roll", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "Egg Roll"


def test_whats_the_cost_of_phrasing(backend):
    intent = backend.parse("what's the cost of the egg roll", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "Egg Roll"


def test_multi_size_item_price_question(backend):
    intent = backend.parse("how much is the wonton soup", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "Wonton Soup"


def test_unmatched_item_short_circuits_unresolved(backend):
    # a price question whose item can't resolve must still short-circuit as
    # item_price (dialog clarifies) - falling through to _parse_items can
    # place a real order (review finding)
    intents = backend.parse("how much is the pepperoni pizza", Context())
    assert [i.kind for i in intents] == ["item_price"]


def test_price_question_does_not_also_add_the_item(backend):
    # a bare "price of X" doesn't start with a recognized question word like
    # "how"/"what" - must not fall through to _parse_items as an order too
    intents = backend.parse("price of the spring roll", Context())
    assert [i.kind for i in intents] == ["item_price"]


def test_price_question_naming_two_items_does_not_add_the_second(backend):
    # review finding: "how much are the egg rolls and crab rangoon" used to
    # chain _parse_items(text) onto the price match, silently emitting an
    # add_item for "crab rangoon" alongside the price answer
    intents = backend.parse("how much are the egg rolls and crab rangoon", Context())
    assert [i.kind for i in intents] == ["item_price"]
    assert intents[0].item_query == "Egg Roll"


def test_price_question_with_comma_joined_items_does_not_add(backend):
    intents = backend.parse("how much is the egg roll, crab rangoon", Context())
    assert [i.kind for i in intents] == ["item_price"]


def test_first_mentioned_item_wins_not_menu_json_order(backend):
    # review finding: resolving the whole remainder as one Menu.find query
    # let the tie-break answer whichever item sits earlier in menu.json
    # (Spring Roll) instead of the one the caller said first
    intents = backend.parse("how much is the wonton soup and the spring roll", Context())
    assert [i.kind for i in intents] == ["item_price"]
    assert intents[0].item_query == "Wonton Soup"


def test_qualifier_collision_price_question_never_orders(backend):
    # review finding: 'chicken' + 'beef' in one utterance made Menu.find
    # reject the whole remainder, and the None fell through to _parse_items,
    # which chunked on 'and' and placed a real Beef with Broccoli order
    intents = backend.parse(
        "how much is the sesame chicken and the beef with broccoli", Context())
    assert [i.kind for i in intents] == ["item_price"]
    assert intents[0].item_query == "Sesame Chicken"


def test_unresolvable_multi_item_price_question_short_circuits(backend):
    intents = backend.parse(
        "how much is the pepperoni pizza and the calzone", Context())
    assert [i.kind for i in intents] == ["item_price"]


def test_and_phrase_dish_names_are_not_split(backend):
    # chunking must mask dish names containing ' and ' (same convention as
    # _parse_items) - 'hot and sour soup' is one item, not two chunks
    intent = backend.parse("how much is the hot and sour soup", Context())[0]
    assert intent.kind == "item_price"
    assert intent.item_query == "Hot and Sour Soup"


# --- dialog: reply text + order untouched ------------------------------------

def test_dialog_states_single_price(session):
    reply = session.handle("how much is General Tso's Chicken")
    assert "$12.50" in reply.text
    assert session.order.lines == []


def test_dialog_states_both_sizes_for_multi_size_item(session):
    reply = session.handle("what does the wonton soup cost")
    assert "$3.50" in reply.text
    assert "$5.95" in reply.text
    assert session.order.lines == []


def test_dialog_unknown_item_never_invents_a_price(session):
    reply = session.handle("how much is the pepperoni pizza")
    assert "$" not in reply.text
    assert session.order.lines == []


def test_dialog_item_price_not_found_branch_never_invents(session):
    # dialog's own guard: an unresolved item_price (RuleBackend's unresolved
    # short-circuit, or HaikuBackend output with no pre-validation) must
    # clarify, never price or order
    reply = session._apply(Intent("item_price", item_query="pepperoni pizza"))
    assert "$" not in reply.text
    assert session.order.lines == []


def test_dialog_price_question_naming_two_items_never_adds_the_second(session):
    # review finding, reproduced at the dialog level: this exact utterance
    # used to answer the egg roll's price AND silently add crab rangoon to
    # the live order
    reply = session.handle("how much are the egg rolls and crab rangoon")
    assert "$1.75" in reply.text
    assert session.order.lines == []


def test_dialog_answers_first_mentioned_item(session):
    reply = session.handle("how much is the wonton soup and the spring roll")
    assert "$3.50" in reply.text
    assert "$5.95" in reply.text
    assert "$1.75" not in reply.text  # spring roll is menu.json-earlier; caller said it second
    assert session.order.lines == []


def test_dialog_qualifier_collision_price_question_places_no_order(session):
    # review finding, exact repro: this utterance used to reply
    # 'Got it - 1 Beef with Broccoli. Anything else?' and mutate the order
    reply = session.handle("how much is the chicken lo mein and the beef with broccoli")
    assert "$6.75" in reply.text
    assert "$10.50" in reply.text
    assert session.order.lines == []


def test_dialog_what_is_the_cost_of_gets_the_price(session):
    reply = session.handle("what is the cost of the egg roll")
    assert "$1.75" in reply.text
    assert session.order.lines == []


def test_dialog_unresolvable_multi_item_price_question_clarifies(session):
    reply = session.handle("how much is the pepperoni pizza and the calzone")
    assert "$" not in reply.text
    assert session.order.lines == []
