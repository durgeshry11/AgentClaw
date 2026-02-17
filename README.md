# TinyClaw

TinyClaw is a **very small local automation toolkit** inspired by OpenClaw-style control loops, designed to stay lightweight and practical.

It includes:
- `tiny_pc_agent.py`: a minimal PC command agent with workspace-bounded paths.
- `tiny_mobile_agent.py`: an Android (ADB) control agent.
- `tiny_ai_agent.py`: a stdlib-only multi-provider AI agent with prompt skills and macro tasks.

All tools use only Python standard library so runtime memory stays low (typically a few MB plus subprocess overhead).

## Goals
- Run with very low RAM.
- Simple, inspectable behavior.
- User-owned API keys for cloud LLMs.
- Reusable skills prompts and macro workflows.

## Requirements
- Python 3.9+
- For mobile control: Android `adb` installed and device connected with USB debugging enabled.
- For AI calls: provider API key in environment variables.

## 1) Tiny PC Agent

### Run
```bash
python3 tiny_pc_agent.py
```

### Example commands
```text
help
run echo hello
write notes.txt this is a note
read notes.txt
list .
quit
```

### Safety model
- Only commands in an allowlist can be executed with `run`.
- File operations are constrained to the current working directory tree.
- `run` path arguments for path-bearing binaries (`cat`, `ls`) are resolved inside the workspace.

## 2) Tiny Mobile Agent (ADB)

### Run
```bash
python3 tiny_mobile_agent.py
```

### Example commands
```text
devices
tap 500 1200
swipe 500 1600 500 500 250
text hello_world
key HOME
open com.android.settings
screenshot screen.png
quit
```

## 3) Tiny AI Agent (OpenAI / Claude / OpenAI-compatible)

### Run
```bash
python3 tiny_ai_agent.py
```

### Provider setup
```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
# Optional model overrides:
export TINY_OPENAI_MODEL=gpt-4o-mini
export TINY_ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

### Commands
```text
providers
skills
skill coder
ask openai skill=coder "write a python function to parse csv safely"
ask anthropic skill=planner "plan a deployment for a small flask app"
ask openai_compat:http://localhost:11434/v1 "summarize this text"
macro add release_flow "ask openai skill=planner plan release ; ask openai skill=qa list test cases"
macro list
macro run release_flow
quit
```

### Skills model
- Skills are prompt presets in `tiny_skills.json`.
- Each skill is an expert instruction block (for example: `planner`, `coder`, `researcher`, `qa`).
- Users can edit or add skills directly without changing code.

### Macro model
- Macros are reusable command sequences in `tiny_macros.json`.
- Each macro stores semicolon-separated Tiny AI Agent commands.
- `macro run <name>` executes steps in order and prints each step/output.

## Minimal architecture
Each agent follows a tiny loop:
1. Parse command input.
2. Validate/sanitize.
3. Execute bounded action.
4. Print compact output.

This keeps logic small enough to inspect and run in low-resource or offline-first setups (except cloud API calls).

## RAM tips
- Keep scripts stdlib-only.
- Avoid local model loading.
- Use short-lived subprocesses.
- Keep prompts concise.

## Disclaimer
TinyClaw is a compact automation foundation, not a full autonomous desktop/mobile framework. For richer orchestration, compose these agents with your own scheduler/UI.
