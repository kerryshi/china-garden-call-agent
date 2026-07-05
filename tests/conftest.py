import pytest

from china_garden.backends import RuleBackend
from china_garden.dialog import DialogSession
from china_garden.faq import Restaurant
from china_garden.menu import Menu


@pytest.fixture(scope="session")
def menu() -> Menu:
    return Menu.load()


@pytest.fixture(scope="session")
def restaurant() -> Restaurant:
    return Restaurant.load()


@pytest.fixture
def session(menu, restaurant) -> DialogSession:
    return DialogSession(menu, restaurant, RuleBackend(menu))
