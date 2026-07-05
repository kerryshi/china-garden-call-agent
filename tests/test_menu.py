def test_exact_name(menu):
    assert menu.find("Egg Roll").id == "egg_roll"


def test_alias(menu):
    assert menu.find("general tso").id == "general_tso"
    assert menu.find("cheese wontons").id == "crab_rangoon"


def test_case_and_punctuation_insensitive(menu):
    assert menu.find("GENERAL TSO'S CHICKEN!").id == "general_tso"


def test_token_subset(menu):
    assert menu.find("wonton").id == "wonton_soup"


def test_no_match_returns_none(menu):
    assert menu.find("pizza") is None
    assert menu.find("") is None


def test_sized_item_has_default(menu):
    soup = menu.find("wonton soup")
    assert soup.default_size.name == "pint"
    assert soup.size_named("quart").price_cents == 595
