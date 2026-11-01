"""Regression tests, no dependency on a runtime, network, or MCP servers."""
from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from mcp_config_translator.cli import DIAGNOSTIC, main, redact
from mcp_config_translator.codecs import parse, render
from mcp_config_translator.model import mismatch_pointers

ROOT = Path(__file__).resolve().parents[1]


class Formats(unittest.TestCase):
    def test_roundtrip_clean_subsets(self) -> None:
        raw = json.loads((ROOT / "examples/vscode.json").read_text())
        copilot = render(parse(raw, "vscode", target="copilot-portable"), "copilot-portable")
        self.assertEqual(json.loads((ROOT / "examples/copilot-portable.json").read_text()), copilot)
        restored = render(parse(copilot, "copilot-portable", target="vscode"), "vscode")
        self.assertEqual(raw, restored)

    def test_paths_with_spaces_and_cwd_loss(self) -> None:
        raw = json.loads((ROOT / "examples/with-cwd.json").read_text())
        a = parse(raw, "vscode")
        self.assertEqual([], a.issues)
        self.assertEqual("C:\\Program Files\\Tools\\mcp-server.exe", a.servers["local"].command)
        other = parse(raw, "vscode", target="copilot-portable")
        self.assertEqual("dropped-cwd", other.issues[0].code)
        result = render(other, "copilot-portable")
        self.assertNotIn("cwd", result["mcpServers"]["local"])
        self.assertEqual(raw["servers"]["local"]["args"], result["mcpServers"]["local"]["args"])

    def test_portable_env_placeholder_translation(self) -> None:
        doc = {"mcpServers": {"x": {"command": "runner", "args": ["${HOME}/file"], "env": {"KEY": "${TOKEN}"}}}}
        converted = render(parse(doc, "copilot-portable", target="vscode"), "vscode")
        self.assertEqual("${env:HOME}/file", converted["servers"]["x"]["args"][0])
        self.assertEqual("${env:TOKEN}", converted["servers"]["x"]["env"]["KEY"])

    def test_fallback_is_untranslatable(self) -> None:
        raw = {"mcpServers": {"x": {"command": "npx", "env": {"K": "${K:-default}"}}}}
        data = parse(raw, "copilot-portable", target="vscode")
        self.assertTrue(any(i.severity == "error" and i.code == "unsupported-reference" for i in data.issues))

    def test_vscode_workspace_macro_cannot_move(self) -> None:
        raw = {"servers": {"x": {"type": "stdio", "command": "python", "args": ["${workspaceFolder}/main.py"]}}}
        result = parse(raw, "vscode", target="copilot-portable")
        self.assertEqual("unsupported-reference", result.issues[0].code)

    def test_unsupported_key_has_explicit_loss(self) -> None:
        raw = {"servers": {"x": {"type": "stdio", "command": "uvx", "sandboxEnabled": True}}}
        converted = parse(raw, "vscode", target="copilot-portable")
        self.assertEqual("unsupported-server-key", converted.issues[0].code)
        self.assertEqual("loss", converted.issues[0].severity)

    def test_portable_local_type_and_unknown_type(self) -> None:
        valid = {"mcpServers": {"x": {"type": "local", "command": "node"}}}
        self.assertEqual([], parse(valid, "copilot-portable").issues)
        valid["mcpServers"]["x"]["type"] = "stdio"
        self.assertEqual("unsupported-transport", parse(valid, "copilot-portable").issues[0].code)

    def test_quoted_executable_ambiguous(self) -> None:
        doc = {"servers": {"x": {"type": "stdio", "command": '"C:/Program Files/foo.exe" --unsafe'}}}
        self.assertEqual("ambiguous-command", parse(doc, "vscode").issues[0].code)

    def test_unknown_transport_is_fatal(self) -> None:
        raw = {"servers": {"x": {"type": "http", "url": "https://example.com"}}}
        result = parse(raw, "vscode")
        self.assertEqual("unsupported-transport", result.issues[0].code)
        self.assertEqual({}, result.servers)

    def test_shell_string_args_rejected(self) -> None:
        raw = {"servers": {"x": {"type": "stdio", "command": "python -m fake", "args": "--unsafe 'quote'"}}}
        codes = {i.code for i in parse(raw, "vscode").issues}
        self.assertIn("ambiguous-command", codes)
        self.assertIn("invalid-args", codes)

    def test_duplicate_name_order_stable(self) -> None:
        raw = {"servers": {"z": {"type": "stdio", "command": "z"}, "a": {"type": "stdio", "command": "a"}}}
        normalized = render(parse(raw, "vscode"), "vscode")
        self.assertEqual(["a", "z"], list(normalized["servers"]))

    def test_json_pointer_escaping(self) -> None:
        self.assertEqual(["/a~1b/x~0y"], mismatch_pointers({"a/b": {"x~y": "yes"}}, {"a/b": {"x~y": "no"}}))

    def test_preview_redaction_secret_values_and_args(self) -> None:
        raw = {"mcpServers": {"x": {"command": "C:/Users/Alice/secret.exe", "args": ["--token=private123", "literal-password-secret"], "env": {"SECRET": "very-private-secret", "REF": "${env:SAFE}"}}}}
        out = json.dumps(redact(raw))
        self.assertNotIn("private123", out)
        self.assertNotIn("very-private-secret", out)
        self.assertNotIn("secret.exe", out)
        self.assertIn("${env:SAFE}", out)

    def test_puzzle_has_exactly_one_canonical_difference(self) -> None:
        a = json.loads((ROOT / "examples/puzzle/vscode.json").read_text())
        b = json.loads((ROOT / "examples/puzzle/copilot.json").read_text())
        l = parse(a, "vscode", target="copilot-portable")
        r = parse(b, "copilot-portable", target="copilot-portable")
        self.assertEqual([], l.issues + r.issues)
        diffs = mismatch_pointers(l.canonical(), r.canonical())
        # Intentionally do not include the expected answer in tracked test code.
        self.assertEqual(1, len(diffs))
        self.assertTrue(diffs[0].startswith("/servers/"))

    def test_absent_empty_roundtrip(self) -> None:
        a = {"servers": {"x": {"type": "stdio", "command": "py", "env": {}, "args": []}}}
        b = render(parse(a, "vscode", target="copilot-portable"), "copilot-portable")
        self.assertEqual({"args": [], "command": "py", "env": {}}, b["mcpServers"]["x"])
        self.assertEqual(a, render(parse(b, "copilot-portable", target="vscode"), "vscode"))


class CommandLine(unittest.TestCase):
    def invoke(self, args: list[str]) -> tuple[int, str, str]:
        output, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(err):
            code = main(args)
        return code, output.getvalue(), err.getvalue()

    def test_requested_validate(self) -> None:
        code, stdout, _ = self.invoke(["validate", str(ROOT / "examples/vscode.json"), "--from", "vscode"])
        self.assertEqual(0, code)
        self.assertIn("OK", stdout)

    def test_requested_dry_run_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "converted.json"
            code, stdout, _ = self.invoke(["convert", str(ROOT / "examples/vscode.json"), "--from", "vscode", "--to", "copilot-portable", "--out", str(output), "--dry-run"])
            self.assertEqual(0, code)
            self.assertFalse(output.exists())
            self.assertIn("DRY RUN", stdout)
            self.assertNotIn("@example/readonly-mcp", stdout)

    def test_convert_write_creates_only_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "result.json"
            args = ["convert", str(ROOT / "examples/vscode.json"), "--from", "vscode", "--to", "copilot-portable", "--out", str(out), "--write"]
            code, _, _ = self.invoke(args)
            self.assertEqual(0, code)
            self.assertEqual(json.loads((ROOT / "examples/copilot-portable.json").read_text()), json.loads(out.read_text()))
            code, _, err = self.invoke(args)
            self.assertEqual(DIAGNOSTIC, code)
            self.assertIn("exists", err)

    def test_lossy_write_requires_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dest.json"
            args = ["convert", str(ROOT / "examples/with-cwd.json"), "--from", "vscode", "--to", "copilot-portable", "--out", str(out), "--write"]
            code, _, err = self.invoke(args)
            self.assertEqual(DIAGNOSTIC, code)
            self.assertFalse(out.exists())
            self.assertIn("dropped-cwd", err)
            code, _, _ = self.invoke(args + ["--allow-loss"])
            self.assertEqual(DIAGNOSTIC, code)  # keeps signal visible to automation
            self.assertTrue(out.exists())

    def test_invalid_shell_not_written_even_with_allow_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp) / "source.json", Path(tmp) / "dest.json"
            src.write_text('{"servers":{"x":{"type":"stdio","command":"python -m unsafe"}}}')
            code, _, err = self.invoke(["convert", str(src), "--from", "vscode", "--to", "copilot-portable", "--out", str(dest), "--write", "--allow-loss"])
            self.assertEqual(DIAGNOSTIC, code)
            self.assertFalse(dest.exists())
            self.assertIn("ambiguous-command", err)

    def test_diff_exposes_paths_not_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "left.json", Path(tmp) / "right.json"
            a.write_text('{"mcpServers":{"x":{"command":"npx","env":{"TOKEN":"supersecretval"}}}}')
            b.write_text('{"mcpServers":{"x":{"command":"npx","env":{"TOKEN":"secondsecretval"}}}}')
            code, stdout, err = self.invoke(["diff", str(a), str(b), "--from", "copilot-portable", "--to", "copilot-portable"])
            self.assertEqual(DIAGNOSTIC, code)
            self.assertIn("/servers/x/env/TOKEN", stdout)
            self.assertNotIn("supersecretval", stdout + err)
            self.assertNotIn("secondsecretval", stdout + err)

    def test_duplicate_json_members_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text('{"servers": {}, "servers": {}}')
            code, _, err = self.invoke(["validate", str(p), "--from", "vscode"])
            self.assertEqual(DIAGNOSTIC, code)
            self.assertIn("duplicate JSON", err)

    def test_no_raw_secret_in_cli_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "secrets.json"
            path.write_text('{"servers":{"test":{"type":"stdio","command":"secretcmd-val","args":["secretarg-value"],"env":{"API_KEY":"super_secret_value"}}}}')
            code, output, err = self.invoke(["convert", str(path), "--from", "vscode", "--to", "copilot-portable"])
            self.assertEqual(0, code)
            self.assertNotIn("super_secret_value", output + err)
            self.assertNotIn("secretarg-value", output + err)
            self.assertNotIn("secretcmd-val", output + err)


if __name__ == "__main__":
    unittest.main()
