#!/bin/sh
set -eu

root="$(cd "$(dirname "$0")" && pwd)"
app="${HERDR_APP_HOME:-$HOME/.config/herdr-app}"

herdr-app "do" layout.switch '{"name":"main"}' >/dev/null || true
rm -f "$app/layouts/lookout.json" "$app/mods/lookout"

python3 - "$root/bin/hook.py" <<'PY'
import json, sys
from pathlib import Path

command = f"python3 {sys.argv[1]}"
settings_path = Path.home() / ".claude/settings.json"
settings = json.loads(settings_path.read_text())
hooks = settings.get("hooks", {})
for event in list(hooks):
    hooks[event] = [g for g in hooks[event] if not any(h.get("command") == command for h in g.get("hooks", []))]
    if not hooks[event]:
        del hooks[event]
settings_path.write_text(json.dumps(settings, indent=2) + "\n")
PY
echo "lookout removed."
