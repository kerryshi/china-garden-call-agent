"""Call simulator - the evidence surface for the conversation core.

  python -m china_garden.cli                 interactive (rule backend)
  python -m china_garden.cli --script demo   scripted demo transcript
  python -m china_garden.cli --backend haiku interactive via cloud Haiku
"""

from __future__ import annotations

import argparse
import sys

from .backends import RuleBackend
from .dialog import DialogSession
from .faq import Restaurant
from .menu import Menu

DEMO_SCRIPT = [
    "hi, what are your hours?",
    "great, can I get two egg rolls and a quart of wonton soup",
    "also one general tso's chicken, extra spicy",
    "actually remove the egg rolls",
    "two egg rolls please",
    "that's it",
    "yes, that's right",
]


def build_session(backend_name: str) -> DialogSession:
    menu = Menu.load()
    restaurant = Restaurant.load()
    if backend_name == "haiku":
        from .backends import HaikuBackend
        backend = HaikuBackend(menu)
    else:
        backend = RuleBackend(menu)
    return DialogSession(menu, restaurant, backend)


def run_script(session: DialogSession, script: list[str]) -> None:
    print(f"AGENT: {session.greeting()}")
    for utterance in script:
        print(f"CALLER: {utterance}")
        reply = session.handle(utterance)
        print(f"AGENT: {reply.text}   [{reply.state}]")
        if reply.done:
            break


def run_interactive(session: DialogSession) -> None:
    print(f"AGENT: {session.greeting()}")
    print("(type 'quit' to exit)")
    while True:
        try:
            utterance = input("CALLER: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if utterance.lower() in ("quit", "exit"):
            break
        reply = session.handle(utterance)
        print(f"AGENT: {reply.text}   [{reply.state}]")
        if reply.done:
            break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="China Garden call simulator")
    parser.add_argument("--script", choices=["demo"], help="run a canned conversation")
    parser.add_argument("--backend", choices=["rule", "haiku"], default="rule")
    args = parser.parse_args(argv)

    session = build_session(args.backend)
    if args.script == "demo":
        run_script(session, DEMO_SCRIPT)
    else:
        run_interactive(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
