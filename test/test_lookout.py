import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugin"))
import view  # noqa: E402


class Render(unittest.TestCase):
    def test_prompt(self):
        self.assertIn("do it", view.render({"type": "user", "message": {"content": "do it"}})[0])

    def test_tool_use_and_text(self):
        entry = {"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls /\nmore"}},
            {"type": "text", "text": "done"},
        ]}}
        out = view.render(entry)
        self.assertIn("Bash", out[0])
        self.assertTrue(out[0].endswith("ls /"))
        self.assertEqual(out[1], "done")
        self.assertNotIn("hidden", "".join(out))

    def test_tool_result_is_clipped(self):
        entry = {"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "a\nb\nc\nd\ne"}]}}
        out = view.render(entry)
        self.assertEqual(len(out), 4)
        self.assertIn("+2 lines", out[-1])

    def test_other_entries_are_hidden(self):
        self.assertEqual(view.render({"type": "attachment"}), [])


class Hook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.record = self.tmp / "record"
        self.record.touch()
        self.env = os.environ | {
            "HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p0", "HERDR_WORKSPACE_ID": "w1",
            "HERDR_BIN_PATH": str(ROOT / "test/stub-herdr"), "STUB_RECORD": str(self.record),
            "LOOKOUT_STATE_DIR": str(self.tmp / "state"), "CLAUDE_CODE_TMPDIR": str(self.tmp),
        }

    def hook(self, event, live=""):
        event = {"session_id": "s1", "transcript_path": "/p/proj/s1.jsonl"} | event
        subprocess.run([sys.executable, ROOT / "plugin/hook.py"], input=json.dumps(event), text=True,
                       env=self.env | {"STUB_LIVE": live}, check=True)
        return self.record.read_text().splitlines()

    def test_first_view_splits_caller_right(self):
        calls = self.hook({"hook_event_name": "SubagentStart", "agent_id": "a1", "agent_type": "Explore"})
        opened = calls[1]
        self.assertIn("--target-pane w1:p0 --direction right", opened)
        self.assertIn("LOOKOUT_PATH=/p/proj/s1/subagents/agent-a1.jsonl", opened)
        self.assertIn("pane rename w1:p2 🤖 Explore", calls[2])

    def test_next_view_stacks_below_live_view(self):
        self.hook({"hook_event_name": "SubagentStart", "agent_id": "a1"})
        calls = self.hook({"hook_event_name": "SubagentStart", "agent_id": "a2"}, live='{"pane_id":"w1:p2"}')
        self.assertIn("--target-pane w1:p2 --direction down", calls[4])

    def test_closed_views_are_forgotten(self):
        self.hook({"hook_event_name": "SubagentStart", "agent_id": "a1"})
        calls = self.hook({"hook_event_name": "SubagentStart", "agent_id": "a2"})
        self.assertIn("--target-pane w1:p0 --direction right", calls[4])

    def test_background_shell(self):
        tasks = self.tmp / f"claude-{os.getuid()}/proj/s1/tasks"
        tasks.mkdir(parents=True)
        calls = self.hook({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                           "tool_input": {"command": "npm test", "run_in_background": True},
                           "tool_response": {"backgroundTaskId": "b1"}})
        self.assertIn(f"LOOKOUT_PATH={tasks}/b1.output", calls[1])
        self.assertIn("pane rename w1:p2 $ npm test", calls[2])

    def test_foreground_shell_is_ignored(self):
        self.assertEqual(self.hook({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                    "tool_input": {"command": "ls"}, "tool_response": {}}), [])

    def test_stop_marks_done(self):
        self.hook({"hook_event_name": "SubagentStop", "agent_id": "a1"})
        self.hook({"hook_event_name": "PostToolUse", "tool_name": "TaskStop", "tool_input": {"task_id": "b1"}})
        self.assertTrue((self.tmp / "state/done/a1").exists())
        self.assertTrue((self.tmp / "state/done/b1").exists())

    def test_outside_herdr_does_nothing(self):
        self.env.pop("HERDR_ENV")
        self.assertEqual(self.hook({"hook_event_name": "SubagentStart", "agent_id": "a1"}), [])


class Follow(unittest.TestCase):
    def test_shell_stops_at_exit_line(self):
        path = Path(tempfile.mkdtemp()) / "b1.output"
        path.write_text("tick\n\n[exited with code 0]\n")
        os.environ |= {"LOOKOUT_DONE": "/nonexistent", "LOOKOUT_SESSION_DONE": "/nonexistent"}
        view.follow(path, "shell")


if __name__ == "__main__":
    unittest.main()
