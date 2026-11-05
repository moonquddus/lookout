# Lookout

A herdr plugin. It shows each Claude Code subagent and each background shell in its own pane.

- The first pane opens to the right of the Claude Code pane. Other panes stack below it.
- A subagent pane shows the prompt, the tool calls, the short tool results and the replies.
- A shell pane shows the live output of the command.
- A pane closes 5 seconds after its work stops.

Foreground shells are not shown, because they stop before Claude Code continues.

## Install

1. Link the plugin:

   ```sh
   herdr plugin link /path/to/lookout
   ```

2. Add these hooks to `~/.claude/settings.json`. Change the path to the plugin:

   ```json
   {
     "hooks": {
       "SubagentStart": [{"hooks": [{"type": "command", "command": "python3 /path/to/lookout/plugin/hook.py", "timeout": 10}]}],
       "SubagentStop": [{"hooks": [{"type": "command", "command": "python3 /path/to/lookout/plugin/hook.py", "timeout": 10}]}],
       "PostToolUse": [{"matcher": "Bash|TaskStop|KillShell", "hooks": [{"type": "command", "command": "python3 /path/to/lookout/plugin/hook.py", "timeout": 10}]}],
       "SessionStart": [{"hooks": [{"type": "command", "command": "python3 /path/to/lookout/plugin/hook.py", "timeout": 10}]}],
       "SessionEnd": [{"hooks": [{"type": "command", "command": "python3 /path/to/lookout/plugin/hook.py", "timeout": 10}]}]
     }
   }
   ```

The hooks do nothing when Claude Code is not in a herdr pane.

## Test

```sh
python3 test/test_lookout.py
```
