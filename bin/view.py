import json
import os
import subprocess
import sys
import time
from pathlib import Path

LINGER_SECONDS = 120
POLL_SECONDS = 0.25
EXIT_MARK = b"[exited with code"
DIM, BOLD, CYAN, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[0m"
SUMMARY_KEYS = ("command", "file_path", "pattern", "url", "query", "description", "prompt")


def report(state, app):
    sys.stdout.write(f"\033]7501;state={state}:app={app}\033\\")
    sys.stdout.flush()


def set_title(title):
    sys.stdout.write(f"\033]2;{title}\a")
    sys.stdout.flush()


def summary(tool_input):
    for key in SUMMARY_KEYS:
        if key in tool_input:
            return str(tool_input[key])
    return json.dumps(tool_input)


def clip(text, lines=3, width=200):
    rows = [row[:width] for row in str(text).splitlines()]
    return rows[:lines] + ([f"… +{len(rows) - lines} lines"] if len(rows) > lines else [])


def result_text(content):
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
    return content or ""


def render(entry):
    message = entry.get("message") or {}
    content = message.get("content")
    if entry.get("type") == "user" and isinstance(content, str):
        return [f"{DIM}▶ {line}{RESET}" for line in clip(content, lines=10)]
    if entry.get("type") not in ("user", "assistant") or not isinstance(content, list):
        return []
    out = []
    for part in content:
        kind = part.get("type")
        if kind == "text" and entry["type"] == "assistant" and part["text"].strip():
            out += [part["text"], ""]
        elif kind == "tool_use":
            line = (summary(part.get("input") or {}).splitlines() or [""])[0][:200]
            out.append(f"{CYAN}●{RESET} {BOLD}{part['name']}{RESET} {line}")
        elif kind == "tool_result":
            out += [f"{DIM}  ⎿ {line}{RESET}" for line in clip(result_text(part.get("content")))]
    return out


def meta(transcript):
    try:
        return json.loads(transcript.with_name(transcript.stem + ".meta.json").read_text())
    except (OSError, ValueError):
        return {}


def hc(*args):
    return subprocess.run(["hc", *args], capture_output=True, text=True, timeout=5)


def kept_in_tab():
    result = hc("get", os.environ["HC_TERMINAL_ID"], "--json")
    return result.returncode == 0 and "herdr.tab" in (json.loads(result.stdout).get("labels") or {})


class Tail:
    def __init__(self, path):
        self.path, self.offset, self.seen, self.last = path, 0, False, b""

    def read(self):
        if not self.path.exists():
            return b""
        self.seen = True
        with self.path.open("rb") as file:
            file.seek(self.offset)
            chunk = file.read()
        self.offset += len(chunk)
        self.last = (self.last + chunk)[-200:]
        return chunk

    def gone(self):
        return self.seen and not self.path.exists()


def follow_agent(path):
    tail, pending, titled = Tail(path), b"", False
    while True:
        info = meta(path)
        if not titled and info.get("description"):
            hc("label", os.environ["HC_TERMINAL_ID"], f"lookout.title={info['description'][:120]}")
            set_title(info["description"])
            titled = True
        chunk = tail.read()
        *lines, pending = (pending + chunk).split(b"\n")
        for line in lines:
            if line.strip():
                rendered = render(json.loads(line))
                if rendered:
                    print("\n".join(rendered), flush=True)
        if (info.get("finished") and not chunk) or tail.gone():
            return
        time.sleep(POLL_SECONDS)


def follow_shell(path):
    tail = Tail(path)
    while True:
        chunk = tail.read()
        if chunk:
            sys.stdout.write(chunk.decode(errors="replace"))
            sys.stdout.flush()
        elif EXIT_MARK in tail.last or tail.gone():
            return
        time.sleep(POLL_SECONDS)


def main():
    kind, path, title = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    app = "claude-code" if kind == "agent" else "shell"
    report("working", app)
    set_title(title)
    print(f"{BOLD}{('🤖 ' if kind == 'agent' else '$ ') + title}{RESET}\n", flush=True)
    (follow_agent if kind == "agent" else follow_shell)(path)
    report("idle", app)
    print(f"\n{DIM}— finished —{RESET}", flush=True)
    deadline = time.monotonic() + LINGER_SECONDS
    while time.monotonic() < deadline or kept_in_tab():
        time.sleep(2)


if __name__ == "__main__":
    main()
