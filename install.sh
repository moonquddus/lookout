#!/bin/sh
set -eu

root="$(cd "$(dirname "$0")" && pwd)"
app="${HERDR_APP_HOME:-$HOME/.config/herdr-app}"

ln -sfn "$root/mod" "$app/mods/lookout"

if [ ! -f "$app/layouts/lookout.json" ]; then
  herdr-app "do" layout.clone '{"name":"main","as":"lookout"}' >/dev/null
fi

python3 - "$app/layouts/lookout.json" "$root/bin/hook.py" <<'PY'
import json, sys
from pathlib import Path

layout_path, hook = Path(sys.argv[1]), sys.argv[2]

def point(node):
    content = node.get("content") or {}
    if content.get("mod") == "agents":
        content["mod"] = "lookout"
    for child in node.get("children", []):
        point(child)

layout = json.loads(layout_path.read_text())
point(layout)
layout_path.write_text(json.dumps(layout, indent=2) + "\n")

settings_path = Path.home() / ".claude/settings.json"
settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
hooks = settings.setdefault("hooks", {})
command = f"python3 {hook}"
wanted = {"SubagentStart": None, "PostToolUse": "Bash|TaskStop|KillShell"}
for event, matcher in wanted.items():
    groups = [g for g in hooks.get(event, []) if not any(h.get("command") == command for h in g.get("hooks", []))]
    group = {"hooks": [{"type": "command", "command": command, "timeout": 10}]}
    if matcher:
        group = {"matcher": matcher, **group}
    hooks[event] = groups + [group]
settings_path.write_text(json.dumps(settings, indent=2) + "\n")
PY

herdr-app "do" layout.switch '{"name":"lookout"}' >/dev/null
herdr-app check "$app/mods/lookout"
echo "lookout installed. Restart Claude Code sessions to load the hooks."
