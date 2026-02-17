# TinyClaw

TinyClaw is a lightweight local automation toolkit for PC, Android, and AI-assisted task execution.

## Included agents
- `tiny_pc_agent.py`: minimal PC command agent with workspace-bounded file safety.
- `tiny_mobile_agent.py`: Android automation wrapper over `adb`.
- `tiny_ai_agent.py`: multi-provider AI task orchestrator with skills, macros, and browser/task automation.

## Requirements
- Python 3.9+
- `adb` for mobile automation
- API keys for AI providers (OpenAI / Anthropic / OpenAI-compatible)

## Tiny AI Agent

### Run
```bash
python3 tiny_ai_agent.py
```

### Environment
```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export TINY_OPENAI_MODEL=gpt-4o-mini
export TINY_ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

### Core commands
```text
providers
skills
ask openai skill=planner "plan migration rollout"
open https://chatgpt.com
run "git status"

# Example from your use case:
task quote_email openai client@example.com "Acme Corp" "Website redesign package with 4-week delivery"

# Generic human-like PC automation (AI-planned action execution):
task auto openai "prepare a quotation workflow: open chatgpt, draft summary, open gmail"

macro add daily_ops "task auto openai check project status ; run git status"
macro run daily_ops
quit
```

## What “human-like PC tasks” means here
The `task auto` workflow lets the AI convert a natural-language goal into an executable JSON plan using supported actions:
- `open_url`
- `run` (allowlisted local binaries)
- `ask` (AI prompt step)
- `wait`

This gives broad, reusable PC-task automation in a lightweight way, and you can chain workflows with macros.

## Quote email workflow
`task quote_email ...` performs:
1. AI generates `subject` + `body` (JSON) using `sales_writer` skill.
2. Opens ChatGPT and Gmail in your browser.
3. Opens Gmail compose with prefilled recipient, subject, and email body.

## Safety and limitations
- `run` in `tiny_ai_agent.py` uses an allowlist for binaries.
- `tiny_pc_agent.py` enforces workspace-bounded paths for path-bearing binaries.
- Full zero-click desktop/browser control for every site/app is not guaranteed in stdlib-only mode (auth prompts, anti-bot checks, dynamic UI).
- Designed for practical automation + human-in-the-loop confirmation for sensitive actions (for example final “Send”).

## Skill presets
Skills are editable in `tiny_skills.json` and include:
- `planner`, `coder`, `researcher`, `qa`, `sales_writer`, `pc_operator`

## Macro presets
Macros are stored in `tiny_macros.json` and can chain any supported commands.
