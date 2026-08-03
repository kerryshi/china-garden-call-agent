"""Regressions from the 2026-07-05 multi-lens review (wf_5e074f11).

Every test here reproduces an evidence-backed finding that failed before the
fix. Grouped by root cause; probe IDs reference the review transcripts.
"""

import pytest

from china_garden.backends import Context, Intent, RuleBackend
from china_garden.dialog import DialogSession


@pytest.fixture
def backend(menu):
    return RuleBackend(menu)


def at_read_back(session):
    session.handle("two egg rolls")
    session.handle("a pint of wonton soup")
    session.handle("that's it")
    assert session.state == "READ_BACK"
    return session


# --- READ_BACK ordering: deny/corrections must outrank confirm -------------

def test_no_thats_not_right_denies(session):
    at_read_back(session)
    session.handle("no, that's not right")
    assert session.state == "ORDERING"  # was: CONFIRMED with a ticket


def test_no_its_not_correct_denies(session):
    at_read_back(session)
    session.handle("no, it's not correct")
    assert session.state == "ORDERING"


def test_yes_but_remove_applies_correction(session):
    at_read_back(session)
    session.handle("yes but remove the egg rolls")
    assert session.state == "ORDERING"  # was: CONFIRMED, correction ignored
    assert "egg_roll" not in [line.item.id for line in session.order.lines]


def test_yes_and_add_reopens_instead_of_confirming(session):
    at_read_back(session)
    reply = session.handle("yes and add an egg roll")
    assert session.state == "ORDERING"
    assert not reply.done
    egg = next(line for line in session.order.lines if line.item.id == "egg_roll")
    assert egg.qty == 3


def test_confirm_with_bye_still_confirms(session):
    at_read_back(session)
    reply = session.handle("yes that's right, bye")
    assert session.state == "CONFIRMED"  # was: goodbye ate the confirm, order lost
    assert reply.done
    assert "PICKUP ORDER" in reply.text


def test_confirm_mentioning_cash_still_confirms(session):
    at_read_back(session)
    reply = session.handle("yes and i'll pay cash at pickup")
    assert session.state == "CONFIRMED"  # was: payment FAQ hijacked the confirm
    assert reply.done


def test_remove_during_read_back_removes(session):
    at_read_back(session)
    session.handle("remove the egg rolls")
    assert session.state == "ORDERING"  # was: added a third egg roll
    assert "egg_roll" not in [line.item.id for line in session.order.lines]


# --- 'and' inside dish names must not split/double -------------------------

def test_hot_and_sour_soup_is_one_item(backend):
    intents = backend.parse("one hot and sour soup", Context())
    assert len(intents) == 1
    assert intents[0].qty == 1


def test_sweet_and_sour_plus_rice(session):
    session.handle("i want the sweet and sour chicken and an order of white rice")
    got = sorted((line.item.id, line.qty) for line in session.order.lines)
    assert got == [("sweet_sour_chicken", 1), ("white_rice", 1)]


# --- allergen hard rule: broadened coverage ---------------------------------

@pytest.mark.parametrize("utterance", [
    "does the lo mein have nuts",
    "is there dairy in that",
    "does it contain soy",
    "does the fried rice contain egg",
    "my kid can't have shrimp, is the fried rice ok",
    "does the sesame chicken have sesame oil in it",
])
def test_allergen_questions_always_hand_off(session, utterance):
    reply = session.handle(utterance)
    assert session.state == "HANDOFF"  # was: item ADDED to the order
    assert reply.done
    assert session.order.lines == []


# --- removal phrasing must never add ----------------------------------------

def test_take_the_x_off_removes(session):
    session.handle("two egg rolls")
    session.handle("take the egg rolls off")
    assert session.order.lines == []  # was: incremented to 3


def test_removal_of_unknown_item_never_adds(session):
    session.handle("remove the pizza")
    assert session.order.lines == []


# --- fuzzy matching: no silent substitutions --------------------------------

@pytest.mark.parametrize("query", ["pork fried rice", "shrimp lo mein", "chicken"])
def test_off_menu_queries_return_none(menu, query):
    assert menu.find(query) is None  # was: White Rice / Chicken Lo Mein / arbitrary


def test_bare_no_does_not_order_noodles(session):
    session.handle("one egg roll")
    session.handle("no")
    ids = [line.item.id for line in session.order.lines]
    assert ids == ["egg_roll"]  # was: added Chicken Lo Mein via 'noodles' substring
    assert session.state == "READ_BACK"  # 'no' after "Anything else?" closes the order


# --- done/FAQ must not swallow items ----------------------------------------

def test_items_and_thats_it_keeps_items(session):
    session.handle("one egg roll")
    session.handle("and two crab rangoon and that's it")
    ids = sorted(line.item.id for line in session.order.lines)
    assert ids == ["crab_rangoon", "egg_roll"]  # was: rangoon silently dropped
    assert session.state == "READ_BACK"


def test_order_plus_faq_keeps_both(session):
    reply = session.handle("can I get two egg rolls and what are your hours")
    assert "Monday" in reply.text
    assert [line.item.id for line in session.order.lines] == ["egg_roll"]
    assert session.order.lines[0].qty == 2  # was: order dropped entirely


# --- questions are not orders ------------------------------------------------

@pytest.mark.parametrize("utterance", [
    "how much is the general tso",
    "do you have egg rolls",
])
def test_price_and_availability_questions_do_not_add(session, utterance):
    session.handle(utterance)
    assert session.order.lines == []  # was: item added with 'Got it'


# --- set_qty ------------------------------------------------------------------

def test_make_that_three(session):
    session.handle("one egg roll")
    session.handle("make that three")
    assert session.order.lines[0].qty == 3  # was: generic fallback, qty stuck


def test_make_it_three_with_item_sets_not_adds(session):
    session.handle("two egg rolls")
    session.handle("actually make it three egg rolls")
    assert session.order.lines[0].qty == 3  # was: additive merge to 5


# --- goodbye guard -------------------------------------------------------------

def test_bye_mid_order_warns_instead_of_losing_order(session):
    session.handle("two egg rolls")
    reply = session.handle("ok bye")
    assert not reply.done  # was: call ended, order silently lost
    assert session.state == "READ_BACK"
    assert "haven't placed" in reply.text


# --- misc parser guards ---------------------------------------------------------

def test_qty_zero_clamped(backend):
    assert backend.parse("0 egg rolls", Context())[0].qty == 1


def test_six_piece_rangoon_is_qty_one(backend):
    intents = backend.parse("6 piece crab rangoon", Context())
    assert intents[0].item_query == "Crab Rangoon (6)"
    assert intents[0].qty == 1  # was: qty 6 -> $35.70


def test_talk_to_someone_hands_off(session):
    reply = session.handle("can i talk to someone")
    assert session.state == "HANDOFF"
    assert reply.done


def test_no_rice_note_survives_menu_collision(backend):
    intent = backend.parse("sesame chicken no rice", Context())[0]
    assert intent.notes == "no rice"  # was: dropped via fuzzy match on White Rice


def test_thats_it_without_apostrophe(session):
    session.handle("an egg roll")
    session.handle("thats it")
    assert session.state == "READ_BACK"


def test_no_thanks_closes_order(session):
    session.handle("an egg roll")
    session.handle("no thanks")
    assert session.state == "READ_BACK"


# --- sized removal ---------------------------------------------------------------

def test_remove_targets_named_size(session):
    session.handle("a pint of wonton soup")
    session.handle("a quart of wonton soup")
    session.handle("remove the quart of wonton soup")
    remaining = session.order.lines
    assert len(remaining) == 1
    assert remaining[0].size.name == "pint"  # was: pint removed instead


# --- state machine: no same-turn read-back + confirm ------------------------------

def test_multi_intent_backend_cannot_confirm_unheard_read_back(menu, restaurant):
    class StubBackend:
        def parse(self, utterance, context):
            return [Intent("add_item", item_query="Egg Roll", qty=2),
                    Intent("done_ordering"), Intent("confirm")]

    session = DialogSession(menu, restaurant, StubBackend())
    reply = session.handle("two egg rolls that's it yes")
    assert session.state == "READ_BACK"  # was: CONFIRMED in one turn
    assert not reply.done


# --- done-phrase remainder: corrections must not become additions ----------
# (2026-08-03 QA battery: "make it two egg rolls, that's all" after ordering
# three merged to FIVE - the done branch fed the remainder to add-parsing)

def test_set_qty_with_done_in_same_breath(session):
    session.handle("three egg rolls")
    session.handle("make it two egg rolls, that's all")
    assert session.state == "READ_BACK"
    assert [(line.item.id, line.qty) for line in session.order.lines] == [
        ("egg_roll", 2)]


def test_removal_with_done_in_same_breath(session):
    session.handle("three egg rolls and a pint of wonton soup")
    session.handle("remove the wonton soup, that's everything")
    assert session.state == "READ_BACK"
    assert [line.item.id for line in session.order.lines] == ["egg_roll"]
