#!/bin/sh
set -eu

root="$(cd "$(dirname "$0")" && pwd)"
app="${HERDR_APP_HOME:-$HOME/.config/herdr-app}"
claude="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

while [ $# -gt 0 ]; do
  case "$1" in
    --claude-dir) claude="$2"; shift 2 ;;
    --claude-dir=*) claude="${1#*=}"; shift ;;
    *) echo "usage: $0 [--claude-dir DIR]" >&2; exit 2 ;;
  esac
done

herdr-app "do" layout.switch '{"name":"main"}' >/dev/null || true
rm -f "$app/layouts/lookout.json" "$app/mods/lookout"

python3 - "$root/bin/hook.py" "$claude" <<'PY'
import json, sys
from pathlib import Path

command = f"python3 {sys.argv[1]}"
settings_path = Path(sys.argv[2]) / "settings.json"
settings = json.loads(settings_path.read_text())
hooks = settings.get("hooks", {})
for event in list(hooks):
    hooks[event] = [g for g in hooks[event] if not any(h.get("command") == command for h in g.get("hooks", []))]
    if not hooks[event]:
        del hooks[event]
settings_path.write_text(json.dumps(settings, indent=2) + "\n")
PY
echo "lookout removed."
