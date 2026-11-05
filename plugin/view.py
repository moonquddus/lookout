import json
import os
import sys
import time
from pathlib import Path

LINGER_SECONDS = 5
DIM, BOLD, CYAN, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[0m"
SUMMARY_KEYS = ("command", "file_path", "pattern", "url", "query", "description", "prompt")


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
        if kind == "text" and entry["type"] == "assistant":
            out += [part["text"], ""]
        elif kind == "tool_use":
            out.append(f"{CYAN}●{RESET} {BOLD}{part['name']}{RESET} {summary(part.get('input') or {}).splitlines()[0][:200]}")
        elif kind == "tool_result":
            out += [f"{DIM}  ⎿ {line}{RESET}" for line in clip(result_text(part.get("content")))]
    return out


def finished(path, kind):
    if Path(os.environ["LOOKOUT_DONE"]).exists() or Path(os.environ["LOOKOUT_SESSION_DONE"]).exists():
        return True
    return kind == "shell" and path.exists() and "[exited with code" in path.read_bytes()[-200:].decode(errors="replace")


def follow(path, kind):
    while not path.exists():
        if finished(path, kind):
            return
        time.sleep(0.2)
    with path.open("rb") as file:
        pending = b""
        while True:
            chunk = file.read()
            if chunk:
                if kind == "shell":
                    sys.stdout.write(chunk.decode(errors="replace"))
                else:
                    pending += chunk
                    *lines, pending = pending.split(b"\n")
                    for line in lines:
                        rendered = render(json.loads(line)) if line.strip() else []
                        if rendered:
                            print("\n".join(rendered))
                sys.stdout.flush()
            elif finished(path, kind):
                return
            else:
                time.sleep(0.2)


def main():
    kind, path, title = os.environ["LOOKOUT_KIND"], Path(os.environ["LOOKOUT_PATH"]), os.environ["LOOKOUT_TITLE"]
    print(f"{BOLD}{'🤖 ' + title if kind == 'agent' else '$ ' + title}{RESET}\n")
    follow(path, kind)
    print(f"\n{DIM}— finished, closing in {LINGER_SECONDS}s —{RESET}")
    time.sleep(LINGER_SECONDS)


if __name__ == "__main__":
    main()
