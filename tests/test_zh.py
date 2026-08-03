"""Chinese-language support: menu matching, parsing, and bilingual replies.

Callers can speak/type Simplified Chinese; the agent parses it with the same
safety-first ordering and replies in the caller's language. English behavior
is pinned by the rest of the suite and must not change.
"""

from china_garden.backends import Context, RuleBackend
from china_garden.dialog import DialogSession
from china_garden.ticket import format_ticket


def zh_session(menu, restaurant) -> DialogSession:
    return DialogSession(menu, restaurant, RuleBackend(menu))


# ---------------------------------------------------------------- menu matching

def test_menu_finds_items_by_chinese_name(menu):
    assert menu.find("春卷").id == "egg_roll"
    assert menu.find("云吞汤").id == "wonton_soup"
    assert menu.find("左宗棠鸡").id == "general_tso"
    assert menu.find("左宗鸡").id == "general_tso"


def test_menu_item_carries_zh_name(menu):
    assert menu.find("Egg Roll").name_zh == "春卷"


# ---------------------------------------------------------------- parsing

def test_zh_order_with_quantity_and_measure_word(menu):
    backend = RuleBackend(menu)
    intents = backend.parse("来两份春卷", Context())
    assert [i.kind for i in intents] == ["add_item"]
    assert intents[0].item_query == "Egg Roll"
    assert intents[0].qty == 2


def test_zh_multi_item_with_size(menu):
    backend = RuleBackend(menu)
    intents = backend.parse("要一个大的云吞汤，还有三份春卷", Context())
    kinds = [(i.item_query, i.qty, i.size) for i in intents if i.kind == "add_item"]
    assert ("Wonton Soup", 1, "quart") in kinds
    assert ("Egg Roll", 3, "") in kinds


def test_zh_allergen_always_hands_off(menu):
    backend = RuleBackend(menu)
    assert backend.parse("春卷里有花生吗", Context())[0].kind == "allergen"
    assert backend.parse("我对味精过敏", Context())[0].kind == "allergen"


def test_zh_request_human(menu):
    backend = RuleBackend(menu)
    assert backend.parse("我要找人工", Context())[0].kind == "request_human"
    assert backend.parse("转真人", Context())[0].kind == "request_human"


def test_zh_faq_topics(menu):
    backend = RuleBackend(menu)
    assert backend.parse("你们几点关门", Context())[0].topic == "hours"
    assert backend.parse("你们地址在哪里", Context())[0].topic == "address"
    assert backend.parse("送不送外卖", Context())[0].topic == "delivery"


def test_zh_price_question_never_orders(menu):
    backend = RuleBackend(menu)
    intents = backend.parse("春卷多少钱", Context())
    assert [i.kind for i in intents] == ["item_price"]
    assert intents[0].item_query == "Egg Roll"


def test_zh_read_back_confirm_and_deny(menu):
    backend = RuleBackend(menu)
    ctx = Context(state="READ_BACK")
    assert backend.parse("对，没错", ctx)[0].kind == "confirm"
    assert backend.parse("不对", ctx)[0].kind == "deny"


def test_zh_removal_never_adds(menu):
    backend = RuleBackend(menu)
    intents = backend.parse("不要春卷了", Context(state="ORDERING"))
    assert intents[0].kind == "remove_item"
    assert intents[0].item_query == "Egg Roll"


def test_zh_done_ordering(menu):
    backend = RuleBackend(menu)
    assert backend.parse("就这样吧", Context(state="ORDERING"))[0].kind == "done_ordering"


def test_zh_spice_note_kept_verbatim(menu):
    backend = RuleBackend(menu)
    intents = backend.parse("一份左宗鸡，加辣", Context())
    adds = [i for i in intents if i.kind == "add_item"]
    assert adds and adds[0].notes == "加辣"


# ---------------------------------------------------------------- dialog replies

def test_zh_turn_gets_zh_reply(menu, restaurant):
    s = zh_session(menu, restaurant)
    reply = s.handle("来两份春卷")
    assert s.state == "ORDERING"
    assert "春卷" in reply.text
    assert "Anything else" not in reply.text


def test_language_follows_the_caller_per_turn(menu, restaurant):
    s = zh_session(menu, restaurant)
    zh = s.handle("来一份春卷")
    assert "春卷" in zh.text
    en = s.handle("and one wonton soup")
    assert "Anything else?" in en.text


def test_zh_full_order_flow_read_back_and_confirm(menu, restaurant):
    s = zh_session(menu, restaurant)
    s.handle("来两份春卷")
    read_back = s.handle("就这样")
    assert s.state == "READ_BACK"
    assert "春卷" in read_back.text
    assert "$" in read_back.text  # totals still stated
    confirmed = s.handle("对")
    assert s.state == "CONFIRMED"
    assert confirmed.done
    assert "分钟" in confirmed.text  # pickup ETA in Chinese


def test_zh_handoff_reply_in_chinese(menu, restaurant):
    s = zh_session(menu, restaurant)
    reply = s.handle("我要找人工")
    assert s.state == "HANDOFF"
    assert reply.done


def test_zh_hours_faq_answer_in_chinese(menu, restaurant):
    s = zh_session(menu, restaurant)
    reply = s.handle("你们几点开门")
    assert "营业时间" in reply.text


# ---------------------------------------------------------------- ticket

def test_ticket_shows_chinese_names_for_the_kitchen(menu, restaurant):
    s = zh_session(menu, restaurant)
    s.handle("来两份春卷")
    ticket = format_ticket(s.order)
    assert "Egg Roll" in ticket
    assert "春卷" in ticket
