def test_greeting_discloses_ai(session):
    text = session.greeting().lower()
    assert "automated" in text or "ai" in text


def test_happy_path_requires_read_back_before_confirm(session):
    session.handle("two egg rolls and a quart of wonton soup")
    assert session.state == "ORDERING"

    reply = session.handle("that's it")
    assert session.state == "READ_BACK"
    assert "read that back" in reply.text.lower()
    assert "2 Egg Roll" in reply.text

    reply = session.handle("yes that's right")
    assert session.state == "CONFIRMED"
    assert reply.done
    assert "PICKUP ORDER" in reply.text  # kitchen ticket emitted


def test_confirm_ignored_outside_read_back(session):
    reply = session.handle("yes")
    assert session.state != "CONFIRMED"
    assert not reply.done


def test_deny_reopens_ordering(session):
    session.handle("an egg roll")
    session.handle("done")
    reply = session.handle("no, that's wrong")
    assert session.state == "ORDERING"
    assert "fix" in reply.text.lower()


def test_done_with_empty_order(session):
    reply = session.handle("that's it")
    assert session.state == "OPEN"
    assert "anything" in reply.text.lower() or "get started" in reply.text.lower()


def test_allergen_hands_off(session):
    reply = session.handle("is there peanut oil in the lo mein?")
    assert session.state == "HANDOFF"
    assert reply.done
    assert "person" in reply.text.lower() or "hand you" in reply.text.lower()


def test_request_human_hands_off(session):
    reply = session.handle("can I talk to a real person")
    assert session.state == "HANDOFF"
    assert reply.done


def test_unknown_item_apologizes(session):
    reply = session.handle("one pepperoni pizza")
    assert "couldn't find" in reply.text.lower() or "didn't catch" in reply.text.lower()
    assert session.order.lines == []


def test_remove_mid_order(session):
    session.handle("two egg rolls")
    session.handle("a general tso")
    session.handle("remove the egg rolls")
    assert [line.item.id for line in session.order.lines] == ["general_tso"]


def test_faq_mid_order_does_not_lose_order(session):
    session.handle("an egg roll")
    session.handle("what are your hours?")
    assert len(session.order.lines) == 1
    assert session.state == "ORDERING"
