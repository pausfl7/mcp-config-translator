# Supported formats & documented boundaries (reviewed 2026-11-01)

## Actual client format 1 — VS Code `.vscode/mcp.json` (`vscode`, `vscode`)

Location: workspace `.vscode/mcp.json` or VS Code user-profile `mcp.json`. Local stdio entries under `servers` require `type: "stdio"`, `command`, and optionally `args`, `env`, `cwd`. Environment references use `${env:NAME}`. VS Code supports additional fields not included here (`envFile`, `inputs`, `dev`, `sandbox`, `sandboxEnabled`, HTTP). Unsupported keys receive diagnostics; these extras are *not* preserved by a cross-format conversion.

Official reference: <https://code.visualstudio.com/docs/agents/reference/mcp-configuration>

## Actual client format 2 — portable Copilot (`copilot-portable`, `copilot-portable`)

Location: workspace-root `.mcp.json`, or Copilot CLI `~/.copilot/mcp-config.json`. Local stdio entries are under `mcpServers` with `command`, `args`, and `env`; GitHub's Copilot CLI examples also use `type: "local"`. This adapter emits the compatible *implicit local command* form to avoid claiming `type: "stdio"` universally supported. References use `${NAME}`. `${NAME:-fallback}` is documented for portable config, but is rejected if converting to VS Code because no lossless equivalent was verified. `cwd` is not supported in **workspace-root portable `.mcp.json`**; our `copilot-portable` adapter deliberately uses that more restrictive subset, even though the Copilot **user** config supports `cwd` according to VS Code's comparison.

Official references:

- <https://code.visualstudio.com/docs/agents/reference/mcp-configuration>
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers>

## Strict subset and exact transformations

- Server mapping is exact on local stdio configs with string `command`, arrays of string `args`, and string-only `env` values. In VS Code, env can also allow numeric and null values; that wider schema is intentionally not represented here.
- Preserve executable paths and arg-array boundaries, including spaces; no shell splitting or quote interpolation is performed.
- `${env:IDENTIFIER}` → `${IDENTIFIER}` from VS Code to portable; reverse in other direction. Do not rewrite `$VAR`, `%VAR%`, unbraced paths, or strings without recognized placeholders. Unmappable `${...}` expressions reject cross-format conversion.
- `cwd` is kept within VS Code validation, but marked as dropped when moving into portable workspace `.mcp.json`; diagnostic `dropped-cwd`. Only `--write --allow-loss` permits a new lossy output.
- Top-level `inputs`, `sandbox`, and unknown server properties are diagnosed and omitted from the conservative model. Don't rely on this tool to merge or translate any custom extensions. `type: "http"` and `type: "sse"` are rejected, not converted.
- This project does not claim current complete schema coverage, an upstream schema version number, or compatibility with every Copilot harness version. The checked **documentation date** is 2026-11-01; reference docs evolve.
