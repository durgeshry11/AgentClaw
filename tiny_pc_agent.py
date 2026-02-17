#!/usr/bin/env python3
"""TinyClaw PC Agent: minimal local automation loop with strict safety bounds."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


ALLOWED_BINARIES = {
    "echo",
    "pwd",
    "date",
    "whoami",
    "uname",
    "ls",
    "cat",
}

BASE_DIR = Path.cwd().resolve()


class AgentError(Exception):
    pass


def _safe_path(user_path: str) -> Path:
    target = (BASE_DIR / user_path).resolve() if not os.path.isabs(user_path) else Path(user_path).resolve()
    if BASE_DIR not in target.parents and target != BASE_DIR:
        raise AgentError("Path outside working directory is blocked.")
    return target


def run_allowed(command: str) -> str:
    parts = shlex.split(command)
    if not parts:
        raise AgentError("Empty command.")
    binary = parts[0]
    if binary not in ALLOWED_BINARIES:
        raise AgentError(f"Blocked binary '{binary}'. Allowed: {', '.join(sorted(ALLOWED_BINARIES))}")

    safe_parts = [binary]
    expects_paths = binary in {"cat", "ls"}
    options_done = False
    for arg in parts[1:]:
        if expects_paths and not options_done and arg == "--":
            options_done = True
            safe_parts.append(arg)
            continue

        if expects_paths and not options_done and arg.startswith("-"):
            safe_parts.append(arg)
            continue

        if expects_paths:
            safe_parts.append(str(_safe_path(arg)))
            continue

        safe_parts.append(arg)

    result = subprocess.run(safe_parts, capture_output=True, text=True, timeout=10)
    out = (result.stdout or "") + (result.stderr or "")
    return out.strip() or f"(exit={result.returncode})"


def read_file(path_text: str) -> str:
    path = _safe_path(path_text)
    if not path.exists() or not path.is_file():
        raise AgentError("File not found.")
    return path.read_text(encoding="utf-8", errors="replace")[:8000]


def write_file(path_text: str, content: str) -> str:
    path = _safe_path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {path}"


def list_dir(path_text: str = ".") -> str:
    path = _safe_path(path_text)
    if not path.exists() or not path.is_dir():
        raise AgentError("Directory not found.")
    return "\n".join(p.name for p in sorted(path.iterdir()))


def help_text() -> str:
    return (
        "Commands:\n"
        "  help\n"
        "  run <shell command>        # allowlisted binaries only\n"
        "  read <path>\n"
        "  write <path> <content>\n"
        "  list [path]\n"
        "  quit"
    )


def dispatch(line: str) -> str:
    if not line.strip():
        return ""
    cmd, *rest = line.strip().split(" ", 1)
    arg = rest[0] if rest else ""

    if cmd == "help":
        return help_text()
    if cmd == "run":
        return run_allowed(arg)
    if cmd == "read":
        return read_file(arg)
    if cmd == "write":
        if not arg:
            raise AgentError("Usage: write <path> <content>")
        parts = arg.split(" ", 1)
        if len(parts) != 2:
            raise AgentError("Usage: write <path> <content>")
        return write_file(parts[0], parts[1])
    if cmd == "list":
        return list_dir(arg or ".")
    if cmd == "quit":
        return "bye"
    raise AgentError("Unknown command. Type: help")


def repl() -> None:
    print("TinyClaw PC Agent. Type 'help' or 'quit'.")
    while True:
        try:
            line = input("pc> ")
        except EOFError:
            print("\nbye")
            return

        try:
            result = dispatch(line)
        except AgentError as e:
            print(f"ERR: {e}")
            continue
        except Exception as e:  # last resort guard
            print(f"ERR: unexpected failure: {e}")
            continue

        if result:
            print(result)
        if line.strip() == "quit":
            return


if __name__ == "__main__":
    repl()
