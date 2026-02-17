#!/usr/bin/env python3
"""TinyClaw Mobile Agent: tiny ADB command wrapper for Android automation."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path


class AgentError(Exception):
    pass


def adb(*args: str) -> str:
    cmd = ["adb", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise AgentError(out.strip() or f"adb failed (exit={result.returncode})")
    return out.strip()


def keycode(name: str) -> str:
    keys = {
        "HOME": "3",
        "BACK": "4",
        "RECENTS": "187",
        "ENTER": "66",
        "POWER": "26",
    }
    code = keys.get(name.upper(), name)
    return adb("shell", "input", "keyevent", code)


def help_text() -> str:
    return (
        "Commands:\n"
        "  help\n"
        "  devices\n"
        "  tap <x> <y>\n"
        "  swipe <x1> <y1> <x2> <y2> [duration_ms]\n"
        "  text <message_with_underscores_for_spaces>\n"
        "  key <HOME|BACK|RECENTS|ENTER|POWER|code>\n"
        "  open <package.name>\n"
        "  screenshot <local_file.png>\n"
        "  quit"
    )


def dispatch(line: str) -> str:
    parts = shlex.split(line)
    if not parts:
        return ""
    cmd, *args = parts

    if cmd == "help":
        return help_text()
    if cmd == "devices":
        return adb("devices")
    if cmd == "tap" and len(args) == 2:
        return adb("shell", "input", "tap", args[0], args[1]) or "ok"
    if cmd == "swipe" and len(args) in (4, 5):
        dur = args[4] if len(args) == 5 else "200"
        return adb("shell", "input", "swipe", args[0], args[1], args[2], args[3], dur) or "ok"
    if cmd == "text" and len(args) == 1:
        return adb("shell", "input", "text", args[0]) or "ok"
    if cmd == "key" and len(args) == 1:
        return keycode(args[0]) or "ok"
    if cmd == "open" and len(args) == 1:
        pkg = args[0]
        return adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
    if cmd == "screenshot" and len(args) == 1:
        local = Path(args[0]).resolve()
        remote = "/sdcard/tinyclaw_screen.png"
        adb("shell", "screencap", "-p", remote)
        adb("pull", remote, str(local))
        return f"saved: {local}"
    if cmd == "quit":
        return "bye"

    raise AgentError("Unknown/invalid command. Type: help")


def repl() -> None:
    print("TinyClaw Mobile Agent (ADB). Type 'help' or 'quit'.")
    while True:
        try:
            line = input("mobile> ")
        except EOFError:
            print("\nbye")
            return

        try:
            out = dispatch(line)
            if out:
                print(out)
            if line.strip() == "quit":
                return
        except AgentError as e:
            print(f"ERR: {e}")
        except Exception as e:
            print(f"ERR: unexpected failure: {e}")


if __name__ == "__main__":
    repl()
