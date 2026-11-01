import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mcp_config_translator.cli import _store_new, main
from mcp_config_translator.codecs import parse


class ReleaseChecks(unittest.TestCase):
    def test_bad_env_and_unknown_field(self):
        server = {"type": "stdio", "command": "node", "env": {"SECRET": ["sensitive"]},
                  "extension": {"value": "sensitive"}}
        issues = parse({"servers": {"test": server}}, "vscode").issues
        self.assertEqual({"unknown-server-key", "invalid-env-entry"}, {i.code for i in issues})
        self.assertNotIn("sensitive", str(issues))

    def test_failed_publication_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch("os.link", side_effect=OSError):
            with self.assertRaises(OSError):
                _store_new(str(Path(tmp) / "config"), "private")
            self.assertEqual([], list(Path(tmp).iterdir()))

    def test_offline_report_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text(json.dumps({"servers": {"x": {"type": "stdio", "command": "never-run",
                "args": [], "env": {"Z": "private", "A": "private"}}}}))
            with patch("subprocess.Popen", side_effect=AssertionError), patch("socket.socket", side_effect=AssertionError):
                output = io.StringIO()
                with redirect_stderr(output), redirect_stdout(io.StringIO()):
                    self.assertEqual(0, main(["convert", str(path), "--from", "vscode", "--to", "copilot-portable"]))
                rows = output.getvalue().splitlines()
                self.assertEqual(sorted(rows), rows)
                self.assertEqual(5, len(rows))
                self.assertNotIn("private", output.getvalue())

    def test_diff_retains_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / n for n in ["a", "b"]]
            for path in paths:
                path.write_text(json.dumps({"servers": {"x": {"type": "stdio", "command": "node", "cwd": path.name}}}))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(3, main(["diff", *map(str, paths), "--left", "vscode", "--right", "vscode"]))
            self.assertEqual(["/servers/x/cwd"], json.loads(out.getvalue())["differences"])
