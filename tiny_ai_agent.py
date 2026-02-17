#!/usr/bin/env python3
"""TinyClaw AI Agent: lightweight multi-provider prompt + macro runner (stdlib only)."""

from __future__ import annotations

import json
import os
import shlex

from pathlib import Path

BASE_DIR = Path.cwd().resolve()
SKILLS_FILE = BASE_DIR / "tiny_skills.json"
MACROS_FILE = BASE_DIR / "tiny_macros.json"
DEFAULT_MODEL_OPENAI = os.getenv("TINY_OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_MODEL_ANTHROPIC = os.getenv("TINY_ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
ALLOWED_RUN_BINARIES = {
    "echo",
    "pwd",
    "date",
    "whoami",
    "uname",
    "ls",
    "cat",
    "python3",
    "git",
    "xdg-open",
    "open",
}


class AgentError(Exception):
    pass


DEFAULT_SKILLS = {
    "planner": "You are an execution planner. Break goals into minimal ordered steps with assumptions.",
    "coder": "You are a senior software engineer. Produce clean, secure, minimal-change code.",
    "researcher": "You are an analyst. Summarize findings, risks, and recommendations.",
    "qa": "You are a QA expert. Propose edge cases and test plans.",
    "sales_writer": "You are a B2B sales writer. Draft concise, professional quotation emails.",
    "pc_operator": (
        "You are a PC operations planner. Convert user goals into executable JSON actions for this agent. "
        "Use only supported action types: open_url, run, ask, wait. "
        "Return ONLY JSON object: {\"actions\":[...]} where each action has type and required fields."
    ),
}


def _ensure_json_file(path: Path, default_obj: dict) -> None:
    if not path.exists():
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
        "  openai_compat:<base_url> (env: OPENAI_API_KEY)"
    )


def build_messages(user_prompt: str, skill_prompt: str | None) -> tuple[str | None, str]:
    return (skill_prompt, user_prompt) if skill_prompt else (None, user_prompt)


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
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    data = _post_json(
        f"{base_url.rstrip('/')}/chat/completions",
        {"Authorization": f"Bearer {api_key}"},
        {"model": DEFAULT_MODEL_OPENAI, "messages": messages, "temperature": 0.2},
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise AgentError(f"Unexpected OpenAI response format: {e}")


def call_anthropic(user_prompt: str, skill_prompt: str | None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AgentError("Missing ANTHROPIC_API_KEY.")
    system, user = build_messages(user_prompt, skill_prompt)
    payload: dict = {
        "model": DEFAULT_MODEL_ANTHROPIC,
        "max_tokens": 800,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        payload["system"] = system
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        payload,
    )
    content = data.get("content")
    if isinstance(content, list):
        return "".join(chunk.get("text", "") for chunk in content).strip()
    return str(content or "").strip()


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


def _extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AgentError("AI response did not contain JSON object.")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise AgentError(f"Failed to parse AI JSON: {e}")
    if not isinstance(payload, dict):
        raise AgentError("AI JSON must be an object.")
    return payload


def open_url(url: str) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise AgentError("Only http(s) URLs are allowed.")
    ok = webbrowser.open(url, new=2)
    return "Opened in browser." if ok else "Browser open requested (headless systems may ignore it)."


def run_local_command(command: str) -> str:
    parts = shlex.split(command)
    if not parts:
        raise AgentError("Empty command.")
    if parts[0] not in ALLOWED_RUN_BINARIES:
        raise AgentError(f"Blocked binary '{parts[0]}'.")
    proc = subprocess.run(parts, capture_output=True, text=True, timeout=30)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return out or f"(exit={proc.returncode})"


def generate_quote_email(provider: str, client_name: str, quotation_details: str) -> tuple[str, str]:
    prompt = (
        "Return ONLY valid JSON with keys subject and body. Draft a concise professional quotation email. "
        f"Client: {client_name}. Details: {quotation_details}."
    )
    payload = _extract_json_object(run_ai(provider, prompt, "sales_writer"))
    subject = str(payload.get("subject", "")).strip()
    body = str(payload.get("body", "")).strip()
    if not subject or not body:
        raise AgentError("AI JSON must include non-empty subject and body.")
    return subject, body


def gmail_compose_url(to_email: str, subject: str, body: str) -> str:
    params = urllib.parse.urlencode({"view": "cm", "fs": "1", "to": to_email, "su": subject, "body": body})
    return f"https://mail.google.com/mail/?{params}"


def task_quote_email(provider: str, to_email: str, client_name: str, quotation_details: str) -> str:
    if "@" not in to_email:
        raise AgentError("Invalid recipient email.")
    subject, body = generate_quote_email(provider, client_name, quotation_details)
    open_url("https://chatgpt.com")
    open_url("https://mail.google.com")
    open_url(gmail_compose_url(to_email, subject, body))
    return f"Draft prepared for {to_email}.\nSubject: {subject}\n\n{body}"


def create_pc_plan(provider: str, goal: str) -> dict:
    prompt = (
        "Goal: "
        + goal
        + "\nCreate executable actions for this agent using only open_url, run, ask, wait. "
        "For ask action include fields provider, skill(optional), prompt. "
        "For run include command. For wait include seconds. Return only JSON."
    )
    return _extract_json_object(run_ai(provider, prompt, "pc_operator"))


def execute_action(action: dict, default_provider: str) -> str:
    action_type = str(action.get("type", "")).strip()
    if action_type == "open_url":
        return open_url(str(action.get("url", "")))
    if action_type == "run":
        return run_local_command(str(action.get("command", "")))
    if action_type == "ask":
        provider = str(action.get("provider") or default_provider)
        skill_val = action.get("skill")
        skill = str(skill_val) if skill_val else None
        prompt = str(action.get("prompt", ""))
        if not prompt:
            raise AgentError("ask action requires prompt.")
        return run_ai(provider, prompt, skill)
    if action_type == "wait":
        seconds = float(action.get("seconds", 1))
        time.sleep(max(0.0, min(seconds, 60.0)))
        return f"Waited {seconds} seconds"
    raise AgentError(f"Unsupported action type '{action_type}'.")


def task_auto(provider: str, goal: str) -> str:
    plan = create_pc_plan(provider, goal)
    actions = plan.get("actions")
    if not isinstance(actions, list):
        raise AgentError("Plan must contain list field 'actions'.")
    outputs = ["Generated plan:", json.dumps(plan, indent=2), "", "Execution:"]
    for i, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise AgentError(f"Action #{i} must be object.")
        outputs.append(f"{i}. {action.get('type', 'unknown')}")
        outputs.append(execute_action(action, provider))
    return "\n".join(outputs)


def help_text() -> str:
    return (
        "Commands:\n"
        "  help\n"
        "  providers\n"
        "  skills\n"
        "  skill <name>\n"
        "  ask <provider> [skill=<name>] <prompt>\n"
        "  open <https-url>\n"
        "  run <local-command>\n"
        "  task quote_email <provider> <to_email> <client_name> <quotation_details>\n"
        "  task auto <provider> <goal>\n"
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
    if cmd == "open":
        if len(parts) != 2:
            raise AgentError("Usage: open <https-url>")
        return open_url(parts[1])
    if cmd == "run":
        if len(parts) < 2:
            raise AgentError("Usage: run <local-command>")
        return run_local_command(" ".join(parts[1:]))
    if cmd == "task":
        if len(parts) < 2:
            raise AgentError("Usage: task <quote_email|auto> ...")
        if parts[1] == "quote_email":
            if len(parts) < 6:
                raise AgentError("Usage: task quote_email <provider> <to_email> <client_name> <quotation_details>")
            return task_quote_email(parts[2], parts[3], parts[4], " ".join(parts[5:]).strip())
        if parts[1] == "auto":
            if len(parts) < 4:
                raise AgentError("Usage: task auto <provider> <goal>")
            return task_auto(parts[2], " ".join(parts[3:]).strip())
        raise AgentError("Usage: task <quote_email|auto> ...")
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
            steps = [x.strip() for x in " ".join(parts[3:]).split(";") if x.strip()]
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
