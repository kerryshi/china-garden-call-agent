"""Catering FAQ topic: 'do you do catering?' / 'big order for pickup' route
through the same FAQ intent path as hours/delivery. The answer is data-backed
from restaurant.json's optional `catering` field; owner confirmed (2026-07-15)
China Garden does NOT cater, so the value politely declines and points to the
person-handoff. When the key is absent, callers get the standard safe fallback."""

import dataclasses

import pytest

from china_garden import faq
from china_garden.backends import Context, RuleBackend


@pytest.fixture
def backend(menu):
    return RuleBackend(menu)


# --- backend: topic detection ------------------------------------------------

def test_do_you_do_catering_detected(backend):
    intent = backend.parse("do you do catering?", Context())[0]
    assert intent.kind == "faq"
    assert intent.topic == "catering"


def test_big_order_for_pickup_detected(backend):
    intent = backend.parse("can I place a big order for pickup", Context())[0]
    assert intent.kind == "faq"
    assert intent.topic == "catering"


# --- faq.answer: data-backed answer + absent-key fallback --------------------

def test_data_backed_catering_answer(restaurant):
    text = faq.answer("catering", restaurant)
    assert "cater" in text.lower()
    # the confirmed decline comes from data, not the generic fallback
    assert "not sure about that one" not in text


def test_absent_key_falls_back_safely(restaurant):
    r = dataclasses.replace(restaurant, catering=None)
    text = faq.answer("catering", r)
    assert "person" in text


# --- dialog: reply text, order untouched, no handoff -------------------------

def test_dialog_catering_declines_without_touching_order(session):
    reply = session.handle("do you do catering?")
    assert "cater" in reply.text.lower()
    assert session.order.lines == []
    # FAQ answer must not trip the allergen/handoff path or advance ordering
    assert reply.state == "OPEN"
    assert reply.done is False
