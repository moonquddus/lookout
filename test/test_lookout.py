import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bin"))

import hook
import view


class HookTest(unittest.TestCase):
    def test_slug_fits_core_names(self):
        self.assertEqual(hook.slug("General Purpose!", 24), "general-purpose")
        self.assertEqual(hook.slug("a" * 40, 24), "a" * 24)
        self.assertEqual(hook.slug("???", 24), "task")


class RenderTest(unittest.TestCase):
    def test_prompt_tool_call_result_and_reply(self):
        prompt = view.render({"type": "user", "message": {"content": "find bugs"}})
        call = view.render(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls\nmore"}}]},
            }
        )
        result = view.render(
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "a\nb\nc\nd"}]}}
        )
        reply = view.render({"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}})
        self.assertIn("find bugs", prompt[0])
        self.assertIn("Bash", call[0])
        self.assertIn("ls", call[0])
        self.assertNotIn("more", call[0])
        self.assertEqual(len(result), 4)
        self.assertEqual(reply, ["done", ""])

    def test_ignores_other_entries(self):
        self.assertEqual(view.render({"type": "attachment"}), [])


class FollowTest(unittest.TestCase):
    def setUp(self):
        view.POLL_SECONDS = 0
        self.dir = Path(tempfile.mkdtemp())

    def test_shell_stops_at_exit_mark(self):
        path = self.dir / "b1.output"
        path.write_text("hello\n\n[exited with code 0]\n")
        out = io.StringIO()
        with redirect_stdout(out):
            view.follow_shell(path)
        self.assertIn("hello", out.getvalue())

    def test_shell_stops_when_file_goes(self):
        path = self.dir / "b2.output"
        path.write_text("hello\n")
        tail = view.Tail(path)
        tail.read()
        path.unlink()
        self.assertTrue(tail.gone())

    def test_shell_finds_output_in_any_session(self):
        path = self.dir / "first-session" / "tasks" / "b3.output"
        path.parent.mkdir(parents=True)
        path.write_text("hello\n\n[exited with code 0]\n")
        out = io.StringIO()
        with redirect_stdout(out):
            view.follow_shell(self.dir / "*" / "tasks" / "b3.output")
        self.assertIn("hello", out.getvalue())

    def test_agent_stops_when_finished(self):
        path = self.dir / "agent-x.jsonl"
        path.write_text(
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n"
        )
        (self.dir / "agent-x.meta.json").write_text(json.dumps({"finished": True}))
        out = io.StringIO()
        with redirect_stdout(out):
            view.follow_agent(path)
        self.assertIn("hi", out.getvalue())


if __name__ == "__main__":
    unittest.main()
