# TinyClaw

TinyClaw is a **very small local automation agent** inspired by OpenClaw-style control loops, designed to stay lightweight and practical.

It includes:
- `tiny_pc_agent.py`: a minimal PC command agent.
- `tiny_mobile_agent.py`: an Android (ADB) control agent.

Both tools use only Python standard library so runtime memory stays low (typically a few MB plus subprocess overhead).

## Goals
- Run with very low RAM (target: under 10 MB for the Python process itself on idle loops).
- Simple, inspectable behavior (no hidden cloud calls).
- Command-driven operation for reliability.

## Requirements
- Python 3.9+
- For mobile control: Android `adb` installed and device connected with USB debugging enabled.

## 1) Tiny PC Agent

### Run
```bash
python3 tiny_pc_agent.py
```

### Example commands
```text
help
run echo hello
read /etc/hostname
write notes.txt this is a note
list .
quit
```

### Safety model
- Only commands in an allowlist can be executed with `run`.
- File operations are constrained to the current working directory tree.

You can customize allowed shell commands by editing `ALLOWED_BINARIES` in `tiny_pc_agent.py`.

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

### Notes
- This agent wraps ADB so it can automate taps/swipes/text/app launch on Android devices.
- For iOS, you'd need a separate backend.

## Minimal architecture
Both agents follow a tiny loop:
1. Parse command line input.
2. Validate/sanitize.
3. Execute a bounded action.
4. Print machine-readable-ish output.

This keeps logic small enough to modify quickly and run on low-resource systems.

## RAM tips (under 10 MB target)
- Keep to stdlib-only scripts (already done).
- Avoid loading large ML models locally.
- Use short-lived subprocesses.
- Avoid background threads.

## Disclaimer
This is a compact automation foundation, not a full autonomous desktop/mobile AI. For richer natural-language planning, integrate a remote LLM endpoint while keeping these local executors as low-RAM action backends.
