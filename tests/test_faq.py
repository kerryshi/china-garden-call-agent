from china_garden import faq


def test_hours_lists_every_day(restaurant):
    text = faq.answer("hours", restaurant)
    for day in ("Monday", "Sunday"):
        assert day in text


def test_address(restaurant):
    assert "3207 S Holden Rd" in faq.answer("address", restaurant)


def test_payment_policy_refuses_card_numbers(restaurant):
    assert "never take card numbers" in faq.answer("payment", restaurant)


def test_unknown_topic_safe_fallback(restaurant):
    assert "person" in faq.answer("what is the meaning of life", restaurant)
