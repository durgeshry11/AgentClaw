#!/usr/bin/env python3
"""TinyClaw AI Agent: lightweight multi-provider prompt + macro runner (stdlib only)."""

from __future__ import annotations

import json
import os
import shlex
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path.cwd().resolve()
SKILLS_FILE = BASE_DIR / "tiny_skills.json"
MACROS_FILE = BASE_DIR / "tiny_macros.json"
DEFAULT_MODEL_OPENAI = os.getenv("TINY_OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_MODEL_ANTHROPIC = os.getenv("TINY_ANTHROPIC_MODEL", "claude-3-5-haiku-latest")


class AgentError(Exception):
    pass


DEFAULT_SKILLS = {
    "planner": (
        "You are an execution planner. Break the user's goal into minimal, ordered steps, "
        "include assumptions, and return concise actionable output."
    ),
    "coder": (
        "You are a senior software engineer. Produce clean, secure, minimal-change code and "
        "include quick validation steps."
    ),
    "researcher": (
        "You are an analyst. Summarize key findings with bullet points, risks, and recommended next actions."
    ),
    "qa": (
        "You are a QA expert. Propose edge cases, reproducible tests, and likely failure modes before sign-off."
    ),
}


def _ensure_json_file(path: Path, default_obj: dict) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(default_obj, indent=2), encoding="utf-8")


def load_skills() -> dict[str, str]:
    _ensure_json_file(SKILLS_FILE, DEFAULT_SKILLS)
    data = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AgentError("tiny_skills.json must contain an object of {name: prompt}.")
    return {str(k): str(v) for k, v in data.items()}


def load_macros() -> dict[str, list[str]]:
    _ensure_json_file(MACROS_FILE, {})
    data = json.loads(MACROS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AgentError("tiny_macros.json must contain an object of {name: [commands]}.")
    out: dict[str, list[str]] = {}
    for name, steps in data.items():
        if not isinstance(steps, list) or not all(isinstance(x, str) for x in steps):
            raise AgentError(f"Macro '{name}' must be a list of command strings.")
        out[str(name)] = list(steps)
    return out


def save_macros(macros: dict[str, list[str]]) -> None:
    MACROS_FILE.write_text(json.dumps(macros, indent=2), encoding="utf-8")


def providers_text() -> str:
    return (
        "Providers:\n"
        "  openai      (env: OPENAI_API_KEY)\n"
        "  anthropic   (env: ANTHROPIC_API_KEY)\n"
        "  openai_compat <base_url> (env: OPENAI_API_KEY)"
    )


def build_messages(user_prompt: str, skill_prompt: str | None) -> tuple[str | None, str]:
    if skill_prompt:
        return skill_prompt, user_prompt
    return None, user_prompt


def _post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise AgentError(f"HTTP {e.code}: {body[:800]}")
    except urllib.error.URLError as e:
        raise AgentError(f"Network error: {e}")


def call_openai(user_prompt: str, skill_prompt: str | None, base_url: str = "https://api.openai.com/v1") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AgentError("Missing OPENAI_API_KEY.")
    system, user = build_messages(user_prompt, skill_prompt)
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    data = _post_json(
        f"{base_url.rstrip('/')}/chat/completions",
        {"Authorization": f"Bearer {api_key}"},
        {
            "model": DEFAULT_MODEL_OPENAI,
            "messages": msgs,
            "temperature": 0.2,
        },
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        raise AgentError("Unexpected OpenAI response format.")


def call_anthropic(user_prompt: str, skill_prompt: str | None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AgentError("Missing ANTHROPIC_API_KEY.")
    system, user = build_messages(user_prompt, skill_prompt)
    payload = {
        "model": DEFAULT_MODEL_ANTHROPIC,
        "max_tokens": 800,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        payload["system"] = system
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        payload,
    )
    try:
        content = data["content"]
        if isinstance(content, list):
            return "".join(chunk.get("text", "") for chunk in content).strip()
        return str(content).strip()
    except Exception:
        raise AgentError("Unexpected Anthropic response format.")


def run_ai(provider: str, prompt: str, skill: str | None) -> str:
    skills = load_skills()
    skill_prompt = None
    if skill:
        if skill not in skills:
            raise AgentError(f"Unknown skill '{skill}'. Use: skills")
        skill_prompt = skills[skill]

    if provider == "openai":
        return call_openai(prompt, skill_prompt)
    if provider == "anthropic":
        return call_anthropic(prompt, skill_prompt)
    if provider.startswith("openai_compat:"):
        base_url = provider.split(":", 1)[1].strip()
        if not base_url:
            raise AgentError("Usage: ask openai_compat:<base_url> [skill=<name>] <prompt>")
        return call_openai(prompt, skill_prompt, base_url=base_url)
    raise AgentError("Unknown provider. Use: providers")


def help_text() -> str:
    return (
        "Commands:\n"
        "  help\n"
        "  providers\n"
        "  skills\n"
        "  skill <name>\n"
        "  ask <provider> [skill=<name>] <prompt>\n"
        "  macro list\n"
        "  macro add <name> <cmd1 ; cmd2 ; ...>\n"
        "  macro run <name>\n"
        "  quit"
    )


def dispatch(line: str) -> str:
    if not line.strip():
        return ""
    parts = shlex.split(line)
    cmd = parts[0]

    if cmd == "help":
        return help_text()
    if cmd == "providers":
        return providers_text()
    if cmd == "skills":
        return "\n".join(sorted(load_skills().keys())) or "(no skills configured)"
    if cmd == "skill":
        if len(parts) != 2:
            raise AgentError("Usage: skill <name>")
        skills = load_skills()
        if parts[1] not in skills:
            raise AgentError("Skill not found.")
        return skills[parts[1]]
    if cmd == "ask":
        if len(parts) < 3:
            raise AgentError("Usage: ask <provider> [skill=<name>] <prompt>")
        provider = parts[1]
        idx = 2
        skill = None
        if idx < len(parts) and parts[idx].startswith("skill="):
            skill = parts[idx].split("=", 1)[1]
            idx += 1
        prompt = " ".join(parts[idx:]).strip()
        if not prompt:
            raise AgentError("Prompt is required.")
        return run_ai(provider, prompt, skill)
    if cmd == "macro":
        if len(parts) < 2:
            raise AgentError("Usage: macro <list|add|run>")
        macros = load_macros()
        sub = parts[1]
        if sub == "list":
            return "\n".join(sorted(macros)) or "(no macros configured)"
        if sub == "add":
            if len(parts) < 4:
                raise AgentError("Usage: macro add <name> <cmd1 ; cmd2 ; ...>")
            name = parts[2]
            raw = " ".join(parts[3:])
            steps = [x.strip() for x in raw.split(";") if x.strip()]
            if not steps:
                raise AgentError("Macro requires at least one step.")
            macros[name] = steps
            save_macros(macros)
            return f"Saved macro '{name}' ({len(steps)} steps)."
        if sub == "run":
            if len(parts) != 3:
                raise AgentError("Usage: macro run <name>")
            name = parts[2]
            if name not in macros:
                raise AgentError("Macro not found.")
            outputs = []
            for step in macros[name]:
                outputs.append(f"> {step}")
                outputs.append(dispatch(step))
            return "\n".join(outputs).strip()
        raise AgentError("Usage: macro <list|add|run>")
    if cmd == "quit":
        return "bye"
    raise AgentError("Unknown command. Type: help")


def repl() -> None:
    print("TinyClaw AI Agent. Type 'help' or 'quit'.")
    while True:
        try:
            line = input("ai> ")
        except EOFError:
            print("\nbye")
            return

        try:
            result = dispatch(line)
        except AgentError as e:
            print(f"ERR: {e}")
            continue
        except Exception as e:
            print(f"ERR: unexpected failure: {e}")
            continue

        if result:
            print(result)
        if line.strip() == "quit":
            return


if __name__ == "__main__":
    repl()
