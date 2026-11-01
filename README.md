# mcp-config-translator

**Convert MCP server config between clients without starting MCP servers.** A small, offline Python CLI for **mcpServers format migration** between VS Code workspace `.vscode/mcp.json` and portable GitHub Copilot workspace `.mcp.json` / Copilot CLI `mcp-config.json` *stdio subsets*. Highlights unsupported fields instead of silently dropping them.

Useful for MCP `env` / `args` / `cwd` configuration conversion, compatibility checks, and inspecting drift between two MCP configurations.

> No servers are started; no network access or telemetry. This tool only reads JSON and, after explicit `--write`, writes a new JSON file. Always review the generated configuration before enabling an MCP client to run it.

## Quick start

Python **3.11+** and pip are the only requirements.

```bash
python -m pip install -e .
mcp-config-translator --help
mcp-config-translator validate examples/vscode.json --from vscode
mcp-config-translator convert examples/vscode.json --from vscode --to copilot-portable --out converted.json --dry-run
```

Expected (checked by tests):

```console
OK: 1 stdio server(s), validated supported subset
DRY RUN: nothing written; preview values redacted
{
  "mcpServers": {
    "demo": {
      "args": [
        "-y",
        "<redacted>"
      ],
      "command": "<redacted>",
      "env": {
        "ACCESS_KEY": "${DEMO_ACCESS_KEY}",
        "LOG_LEVEL": "<redacted>"
      }
    }
  }
}
```

The `@example/readonly-mcp` package name in these fixtures is intentionally illustrative, **not an installed or verified MCP package**. Do not enable it as a real server.

The preview above is stdout. A sorted field report on stderr identifies each preserved setting or loss.

To actually create a config, **explicitly** select a new output file:

```bash
mcp-config-translator convert examples/vscode.json --from vscode --to copilot-portable --out converted.json --write
mcp-config-translator validate converted.json --from copilot-portable
mcp-config-translator diff examples/vscode.json converted.json --left vscode --right copilot-portable
```

To complete the round trip, run `mcp-config-translator convert converted.json --from copilot-portable --to vscode --out restored.json --write`. Comparing restored.json and examples/vscode.json with `diff --left vscode --right vscode` gives an empty differences array.

The `--write` output retains literal env values and arguments needed to run a server; it is **not** a sanitized file, and must not be committed if it contains credentials. Unlike dry-run, it is a new file with restrictive permissions on POSIX (0600); Windows ACLs depend on the containing directory. Existing files are **never overwritten**.

```bash
# Inspect cwd compatibility loss without writing anything
mcp-config-translator convert examples/with-cwd.json --from vscode --to copilot-portable
# If you have reviewed that loss and accept it:
mcp-config-translator convert examples/with-cwd.json --from vscode --to copilot-portable --out converted.json --write --allow-loss
```

The second command returns exit code 3 because the `cwd` loss remains a diagnostic, even if the new file is created. Choose a different output path if `converted.json` already exists.

## What is actually translated?

| Field | VS Code workspace (`vscode`) | Copilot portable (`copilot-portable`) | Conversion |
| --- | --- | --- | --- |
| Top-level servers | `servers` | `mcpServers` | Rename |
| stdio transport | `type: "stdio"` | implicit local stdio (`type: "local"` also read) | Normalize |
| Executable | `command` | `command` | Preserve (never execute) |
| Args | array of strings | array of strings | Preserve array boundaries |
| Env | string values | string values | Preserve literal values in written output |
| Environment reference | `${env:NAME}` | `${NAME}` | Translate supported forms |
| `cwd` | supported | unsupported in workspace-root `.mcp.json` | Report and drop only with explicit opt-in to write |
| Input prompts, `envFile`, `dev`, sandbox, remote HTTP, tools | outside safe subset | outside safe subset | Report; **not** automatically migrated |

We do **not** split shell strings. If `command` looks like `python -m server`, we reject it: write `"command":"python","args":["-m","server"]` instead. A Windows executable path with spaces stays a single string. A portable `${VAR:-fallback}` reference cannot map exactly into the VS Code syntax, so conversion refuses it. JSON keys are sorted, arrays retain order, and duplicate JSON object keys are rejected.

`diff` normalizes both inputs to the same supported canonical model and prints **JSON Pointers only**, never changed values:

```bash
mcp-config-translator diff examples/vscode.json examples/copilot-portable.json --from vscode --to copilot-portable
# -> {"differences": [], "equal": true} (formatted as JSON)
```

Exit codes: **0** clean success; **2** command-line usage; **3** validation issues, unsupported/lossy conversion, or detected drift / file errors. Warning/loss diagnostics are printed to stderr without secrets.

## Install on Windows / Linux

**PowerShell (Windows):**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
mcp-config-translator --help
python -m unittest discover -s tests -v
```

**Linux (bash):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
mcp-config-translator --help
python -m unittest discover -s tests -v
```

Alternative without installing, from the repo root: `PYTHONPATH=src python -m mcp_config_translator --help` (Windows PowerShell: `$env:PYTHONPATH='src'; python -m mcp_config_translator --help`). CI exercises Python 3.11 and 3.13 on Windows and Linux.

## Safety & scope

- **Offline:** the code performs no network requests, imports no MCP runtime, and never calls a server command.
- **Dry-run is default**, including when `--out` is provided. Terminal previews hide commands, nontrivial args, and literal env values. `diff` prints paths only.
- **Secrets:** a written output intentionally preserves literal credentials; inspect and protect it. Diagnostic output cannot guarantee secrecy of user-chosen *JSON keys, server IDs, or filesystem path arguments*; don't place secrets in those names.
- **Losses:** unsupported properties are excluded from the supported model, explicitly diagnosed, and block writes unless `--allow-loss` is supplied. Unrepresentable shell syntax and references block conversion even with that switch.
- **Boundaries:** local stdio server subset only. No HTTP/SSE, interactive VS Code inputs, arbitrary per-client extensions, global scope mergers, sandbox setting mapping, credential-store integration, or runtime validation. An actual client may support extra fields; this conservative tool does not claim to migrate them.
- **Trust:** do not open/move an untrusted config into an executable client without reviewing the server command and arguments. Converting it is not running it.

See [the exact compatibility and source references](docs/formats.md), [testing notes](docs/testing.md), and [contribution guidance](AGENTS.md).

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

This MIT-licensed project is a deliberately narrow converter, not a universal MCP schema validator. Contributions should include official schema references, a loss behavior decision, and regression tests.
