import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

VIEW = Path(__file__).with_name("view.py")


def slug(text, length):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:length] or "task"


def task_output(event, task):
    project = Path(event["transcript_path"]).parent.name
    roots = [os.environ.get("CLAUDE_CODE_TMPDIR"), tempfile.gettempdir(), "/private/tmp", "/tmp"]
    projects = [Path(root) / f"claude-{os.getuid()}" / project for root in roots if root]
    base = next((path for path in projects if path.is_dir()), projects[0])
    # A resumed session keeps writing tasks under the session it started as, so match any session.
    return base / "*" / "tasks" / f"{task}.output"


def start(event, kind, key, path, title):
    subprocess.run(
        [
            "hc",
            "run",
            "--bg",
            "--rm",
            "--no-notify",
            "--json",
            "--name",
            f"{'sub' if kind == 'agent' else 'sh'}-{slug(key, 24)}",
            "--cwd",
            event.get("cwd") or os.getcwd(),
            "--label",
            f"lookout.kind={kind}",
            "--label",
            f"lookout.title={title[:120]}",
            "--",
            sys.executable,
            str(VIEW),
            kind,
            str(path),
            title,
        ],
        capture_output=True,
        timeout=8,
        check=True,
    )


def main():
    if "HC_TERMINAL_ID" not in os.environ:
        return
    event = json.load(sys.stdin)
    name = event.get("hook_event_name")
    if name == "SubagentStart":
        agent_id = event["agent_id"]
        path = Path(event["transcript_path"]).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"
        start(event, "agent", agent_id, path, event.get("agent_type") or "agent")
    elif name == "PostToolUse" and event.get("tool_name") == "Bash":
        task = (event.get("tool_response") or {}).get("backgroundTaskId")
        if task:
            tool_input = event.get("tool_input") or {}
            start(
                event,
                "shell",
                task,
                task_output(event, task),
                tool_input.get("description") or tool_input.get("command", ""),
            )
    elif name == "PostToolUse" and event.get("tool_name") in ("TaskStop", "KillShell"):
        tool_input = event.get("tool_input") or {}
        task = tool_input.get("task_id") or tool_input.get("shell_id")
        if task:
            subprocess.run(["hc", "kill", f"sh-{slug(task, 24)}"], capture_output=True, timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"lookout: {error}", file=sys.stderr)
