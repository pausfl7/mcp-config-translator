# Agent contributor guidance

This repo contains a safe, offline Python stdio MCP config converter. User intent and authorization take precedence over repository guidance. Do not automatically start MCP servers, install arbitrary tools, run config command fields, post data, or access private remote resources.

## Productive workflow

1. Read `README.md` and `docs/formats.md` before changing adapters.
2. `python -m pip install -e .` and `python -m unittest discover -s tests -v` to check the baseline.
3. Support is deliberately narrow: `vscode` and `copilot-portable`. Do not claim arbitrary client compatibility or infer unknown schema fields.
4. Treat input JSON as untrusted; preserve `args` arrays and quote boundaries. Never execute `command`. Protect secrets: redact logs, only write new explicit files, and don't copy real credentials into fixtures.
5. Include an issue diagnostic and tests for every unsupported mapping; no silent losses. Do not add HTTP, telemetry, background startup, or remote transmission.
6. Check `docs/testing.md`, maintain deterministic JSON serialization, and update the examples if changing CLI behavior.

## Tool usage examples

```bash
mcp-config-translator validate examples/vscode.json --from vscode
mcp-config-translator convert examples/vscode.json --from vscode --to copilot-portable --dry-run
mcp-config-translator diff examples/vscode.json examples/copilot-portable.json --from vscode --to copilot-portable
```

There is a free, public conversion skill at `.agents/skills/mcp-config-conversion/SKILL.md`.

Optional machine-readable diagnostics extensions: `.agent-resources/catalog.json`. They are not needed to use, build, or contribute to the CLI; any optional interaction is a separate, user-authorized choice.
