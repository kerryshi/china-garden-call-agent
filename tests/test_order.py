import pytest

from china_garden.order import Order


@pytest.fixture
def order(restaurant):
    return Order(sales_tax_bps=restaurant.sales_tax_bps)


def test_add_and_totals(order, menu):
    order.add(menu.find("egg roll"), qty=2)                # 2 x 175 = 350
    order.add(menu.find("wonton soup"), size_name="quart")  # 595
    assert order.subtotal_cents == 945
    # 6.75% of 945 = 63.7875 -> rounds to 64
    assert order.tax_cents == 64
    assert order.total_cents == 1009


def test_same_item_same_size_merges(order, menu):
    order.add(menu.find("egg roll"), qty=1)
    order.add(menu.find("egg roll"), qty=2)
    assert len(order.lines) == 1
    assert order.lines[0].qty == 3


def test_different_sizes_do_not_merge(order, menu):
    order.add(menu.find("wonton soup"), size_name="pint")
    order.add(menu.find("wonton soup"), size_name="quart")
    assert len(order.lines) == 2


def test_remove(order, menu):
    order.add(menu.find("egg roll"))
    line = order.find_line(menu.find("egg roll"))
    order.remove(line)
    assert order.lines == []
    assert order.total_cents == 0


def test_read_back_contains_every_line_and_total(order, menu):
    order.add(menu.find("egg roll"), qty=2)
    order.add(menu.find("general tso"), notes="extra spicy")
    text = order.read_back()
    assert "2 Egg Roll" in text
    assert "General Tso's Chicken" in text
    assert "extra spicy" in text
    assert "$16.00" in text          # subtotal 350 + 1250
    assert "total" in text.lower()


def test_read_back_empty(order):
    assert "empty" in order.read_back().lower()


def test_tax_rounding_half_up(menu):
    order = Order(sales_tax_bps=675)
    order.add(menu.find("egg roll"), qty=2)  # 350 -> tax 23.625 -> 24
    assert order.tax_cents == 24
