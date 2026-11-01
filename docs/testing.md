# Tests & reproducibility

All tests use Python `unittest` from the standard library and offline example files.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
mcp-config-translator validate examples/vscode.json --from vscode
mcp-config-translator convert examples/vscode.json --from vscode --to copilot-portable --out converted.json --dry-run
mcp-config-translator diff examples/vscode.json examples/copilot-portable.json --from vscode --to copilot-portable
```

`converted.json` should **not exist** after dry-run. The clean diff result has `"equal": true`. `examples/with-cwd.json` must emit `dropped-cwd` and exit 3 when converted to copilot-portable; `--write` without `--allow-loss` refuses any new file. The public puzzle fixtures are checked for exactly one canonical mismatched leaf, but the private acceptance answer is intentionally not included in tracked tests.

Tested here on CPython 3.12.14 (and `pyproject.toml` supports 3.11+). GitHub Actions is configured to test Windows and Linux Python 3.11/3.13 after you publish, but no CI run is claimed before the repository is pushed.

No integration test opens VS Code or Copilot. Syntax and field support were compared against the official public documentation on 2026-11-01; actual behavior depends on the runtime/client version.
