"""Handoff order briefing: the human picking up a HANDOFF must not be blind
to an order in progress. Reply.order_summary carries the structured,
caller-safe snapshot; reply.text gets a natural confirmation line.
"""


def test_allergen_handoff_with_order_carries_summary(session):
    session.handle("two egg rolls")
    reply = session.handle("is there peanut oil in that")
    assert session.state == "HANDOFF"
    assert reply.done
    assert reply.order_summary == [
        {"item": "Egg Roll", "qty": 2, "size": "", "notes": ""},
    ]
    assert "saved" in reply.text.lower()


def test_request_human_handoff_with_order_carries_summary(session):
    session.handle("a quart of wonton soup")
    reply = session.handle("let me talk to a person")
    assert session.state == "HANDOFF"
    assert reply.done
    assert reply.order_summary == [
        {"item": "Wonton Soup", "qty": 1, "size": "quart", "notes": ""},
    ]
    assert "saved" in reply.text.lower()


def test_handoff_summary_covers_multiple_lines_with_size_and_notes(session):
    session.handle("a quart of wonton soup")
    session.handle("one general tso's chicken, extra spicy")
    reply = session.handle("can I talk to a real person")
    assert reply.order_summary == [
        {"item": "Wonton Soup", "qty": 1, "size": "quart", "notes": ""},
        {"item": "General Tso's Chicken", "qty": 1, "size": "", "notes": "extra spicy"},
    ]


def test_allergen_handoff_without_order_has_no_summary(session):
    reply = session.handle("is there peanut oil in the lo mein?")
    assert session.state == "HANDOFF"
    assert reply.done
    assert reply.order_summary is None
    assert "saved" not in reply.text.lower()


def test_request_human_handoff_without_order_has_no_summary(session):
    reply = session.handle("can I talk to a real person")
    assert session.state == "HANDOFF"
    assert reply.done
    assert reply.order_summary is None
    assert "saved" not in reply.text.lower()


def test_handoff_text_never_leaks_internal_notation(session):
    session.handle("two egg rolls")
    session.handle("a general tso")
    reply = session.handle("is there peanut oil in that")
    assert "egg_roll" not in reply.text
    assert "general_tso" not in reply.text
    assert "{" not in reply.text and "}" not in reply.text


def test_non_handoff_reply_has_no_order_summary(session):
    reply = session.handle("two egg rolls")
    assert reply.order_summary is None
    reply = session.handle("that's it")
    assert session.state == "READ_BACK"
    assert reply.order_summary is None
