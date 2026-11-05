import fcntl
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

STATE = Path(os.environ.get("LOOKOUT_STATE_DIR", Path.home() / ".local/state/herdr/plugins/lookout"))


def herdr(*args):
    result = subprocess.run([os.environ.get("HERDR_BIN_PATH", "herdr"), *args],
                            capture_output=True, text=True, check=True).stdout
    return json.loads(result) if result.strip() else {}


def mark_done(key):
    (STATE / "done").mkdir(parents=True, exist_ok=True)
    (STATE / "done" / key).touch()


def tasks_dir(event):
    transcript = Path(event["transcript_path"])
    roots = [os.environ.get("CLAUDE_CODE_TMPDIR"), tempfile.gettempdir(), "/private/tmp", "/tmp"]
    candidates = [Path(root) / f"claude-{os.getuid()}" / transcript.parent.name / event["session_id"] / "tasks"
                  for root in roots if root]
    return next((path for path in candidates if path.is_dir()), candidates[0])


def target(event):
    name = event["hook_event_name"]
    if name == "SubagentStart":
        transcript = Path(event["transcript_path"])
        path = transcript.with_suffix("") / "subagents" / f"agent-{event['agent_id']}.jsonl"
        return "agent", event["agent_id"], path, event.get("agent_type") or "agent"
    if name == "PostToolUse" and event.get("tool_name") == "Bash":
        task = (event.get("tool_response") or {}).get("backgroundTaskId")
        if task:
            tool_input = event["tool_input"]
            return "shell", task, tasks_dir(event) / f"{task}.output", tool_input.get("description") or tool_input["command"]
    return None


def live_panes(workspace):
    panes = herdr("pane", "list", "--workspace", workspace)["result"]["panes"]
    return {pane["pane_id"] for pane in panes}


def open_view(event, kind, key, path, title):
    caller = os.environ["HERDR_PANE_ID"]
    STATE.mkdir(parents=True, exist_ok=True)
    slug = caller.replace(":", "_")
    # Parallel subagents start at the same time. One hook at a time changes the layout.
    with (STATE / f"{slug}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        column_file = STATE / f"{slug}.json"
        column = json.loads(column_file.read_text()) if column_file.exists() else []
        live = live_panes(os.environ["HERDR_WORKSPACE_ID"])
        column = [pane for pane in column if pane in live]
        anchor, direction = (column[-1], "down") if column else (caller, "right")
        env = {
            "LOOKOUT_KIND": kind,
            "LOOKOUT_PATH": str(path),
            "LOOKOUT_TITLE": title,
            "LOOKOUT_DONE": str(STATE / "done" / key),
            "LOOKOUT_SESSION_DONE": str(STATE / "done" / event["session_id"]),
        }
        opened = herdr("plugin", "pane", "open", "--plugin", "lookout", "--entrypoint", "view",
                       "--target-pane", anchor, "--direction", direction, "--no-focus",
                       *[arg for name, value in env.items() for arg in ("--env", f"{name}={value}")])
        pane = opened["result"]["plugin_pane"]["pane"]["pane_id"]
        herdr("pane", "rename", pane, f"{'🤖' if kind == 'agent' else '$'} {title}"[:60])
        column_file.write_text(json.dumps(column + [pane]))


def main():
    if os.environ.get("HERDR_ENV") != "1" or "HERDR_PANE_ID" not in os.environ:
        return
    event = json.load(sys.stdin)
    name = event["hook_event_name"]
    if name == "SessionStart":
        (STATE / "done" / event["session_id"]).unlink(missing_ok=True)
    elif name == "SessionEnd":
        mark_done(event["session_id"])
    elif name == "SubagentStop":
        mark_done(event["agent_id"])
    elif name == "PostToolUse" and event.get("tool_name") in ("TaskStop", "KillShell"):
        tool_input = event.get("tool_input") or {}
        task = tool_input.get("task_id") or tool_input.get("shell_id")
        if task:
            mark_done(task)
    elif found := target(event):
        open_view(event, *found)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"lookout: {error}", file=sys.stderr)
