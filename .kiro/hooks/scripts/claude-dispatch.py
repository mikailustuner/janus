#!/usr/bin/env python3
"""Run the Kiro PostFileSave hooks from Claude Code.

Claude Code calls this after Write/Edit with the tool call as JSON on stdin. The script
reads every enabled hook in .kiro/hooks/*.json whose trigger is PostFileSave, matches the
edited path against the hook's regex and runs its command from the repository root, as
Kiro does. Exit code 2 sends the hook's findings back to the agent.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    try:
        call = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = str((call.get("tool_input") or {}).get("file_path") or "")
    if not path:
        return 0
    failures: list[str] = []
    for spec in sorted((ROOT / ".kiro" / "hooks").glob("*.json")):
        data = json.loads(spec.read_text(encoding="utf-8"))
        for hook in data.get("hooks", []):
            if hook.get("enabled") is False or hook.get("trigger") != "PostFileSave":
                continue
            action = hook.get("action") or {}
            if action.get("type") != "command" or not re.search(hook.get("matcher", "$^"), path):
                continue
            done = subprocess.run(
                action["command"],
                shell=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=int(action.get("timeout", 60)),
            )
            if done.returncode != 0:
                failures.append(f"[{hook.get('name')}]\n{(done.stdout + done.stderr).strip()}")
    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
