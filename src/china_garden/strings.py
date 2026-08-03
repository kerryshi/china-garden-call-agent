"""Reply templates, English and Simplified Chinese.

The English strings are the originals from dialog.py verbatim - the whole
regression suite pins them. zh wording is a draft for Kerry/family review.
"""

from __future__ import annotations

REPLIES: dict[str, dict[str, str]] = {
    "en": {
        "handoff_person": "No problem - one moment while I get a person for you.",
        "saved_order_suffix": ("\nI've saved your order so far - the person you're "
                               "speaking with can see it."),
        "goodbye_unplaced": ("Before you go - I haven't placed your order yet. "
                             "{read_back}\nShould I place it?"),
        "goodbye": "Thanks for calling {name} - bye now!",
        "unknown_item": ("Sorry, I couldn't find '{query}' on our menu - "
                         "could you say it another way?"),
        "price_unsure": ("Sorry, I'm not sure which item you mean - could you say it "
                         "another way?"),
        "size_choice": "{name} comes in {options} - which would you like?",
        "qty_check": "Just to check - did you really want {qty} of the {name}?",
        "added": "Got it - {desc}. Anything else?",
        "removed": "Removed {desc}. Anything else?",
        "not_on_order": "I don't see that on your order - what should I remove?",
        "which_change": "Which item should I change?",
        "removed_name": "Removed {name}. Anything else?",
        "okay": "Okay - {desc}. Anything else?",
        "nothing_yet": ("I don't have anything on your order yet - what can I "
                        "get started for you?"),
        "read_back_q": "{read_back}\nIs that all correct?",
        "confirmed": ("You're all set - it'll be ready for pickup in about "
                      "{eta} minutes. See you soon!\n{ticket}"),
        "fix_what": "Sorry about that - what should I fix?",
        "fallback": ("Sorry, I didn't catch that - you can order, ask about hours "
                     "or delivery, or say 'person' for a human."),
    },
    "zh": {
        "handoff_person": "好的——请稍等，我帮您转真人。",
        "saved_order_suffix": "\n您目前点的单我已经保存——接听的工作人员可以看到。",
        "goodbye_unplaced": "先别挂——您的订单我还没有下。{read_back}\n要帮您下单吗？",
        "goodbye": "谢谢来电{name}，再见！",
        "unknown_item": "不好意思，菜单上没找到“{query}”——您能换个说法吗？",
        "price_unsure": "不好意思，我不确定您说的是哪道菜——您能换个说法吗？",
        "size_choice": "{name}有{options}——您要哪种？",
        "qty_check": "跟您确认一下——您真的要{qty}份{name}吗？",
        "added": "好的——{desc}。还要别的吗？",
        "removed": "已去掉{desc}。还要别的吗？",
        "not_on_order": "您的订单里没有这个——要去掉哪一样？",
        "which_change": "要改哪一样？",
        "removed_name": "已去掉{name}。还要别的吗？",
        "okay": "好的——{desc}。还要别的吗？",
        "nothing_yet": "您还没有点任何东西——想来点什么？",
        "read_back_q": "{read_back}\n请问都对吗？",
        "confirmed": "好的，订单已确认——大约{eta}分钟后就可以来取餐了。谢谢！\n{ticket}",
        "fix_what": "不好意思——要改哪里？",
        "fallback": ("不好意思，我没听明白——您可以点餐、询问营业时间或外卖，"
                     "也可以说“人工”转真人。"),
    },
}


def t(lang: str, key: str, **kwargs: object) -> str:
    table = REPLIES.get(lang, REPLIES["en"])
    template = table.get(key) or REPLIES["en"][key]
    return template.format(**kwargs)
