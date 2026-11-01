---
name: mcp-config-conversion
description: Convert and validate local stdio MCP server JSON between VS Code .vscode/mcp.json and portable Copilot mcpServers files, without starting servers. Use when asked for a reversible, reviewable MCP client config migration or JSON Pointer diff.
license: MIT
compatibility: Python 3.11+ and mcp-config-translator installed; offline.
---

# MCP config conversion (free public skill)

Use this skill when a user requests a safe MCP client config conversion, `mcpServers` migration, or comparison of two local server configs. Follow the user's authorization and do not run imported server commands.

1. Identify source and destination: VS Code workspace `servers` = `vscode` (`vscode`), portable Copilot `mcpServers` = `copilot-portable` (`copilot-portable`). Read `docs/formats.md` for precise coverage.
2. Run `mcp-config-translator validate path.json --from vscode`. Review warnings; abort for errors and ask for or suggest manual adjustments to unrecognized fields.
3. Preview: `mcp-config-translator convert path.json --from vscode --to copilot-portable --dry-run`. Treat exit code 3 as a meaningful warning/error, not proof of complete migration.
4. If a user explicitly authorizes writing, choose a **new file** and run `mcp-config-translator convert path.json --from vscode --to copilot-portable --out migrated.mcp.json --write`. If the output would omit `cwd` or other fields, explain the exact loss and require explicit approval before adding `--allow-loss`.
5. Review both generated and source files in the user's environment (protect credentials). Run `mcp-config-translator validate migrated.mcp.json --from copilot-portable` and `mcp-config-translator diff path.json migrated.mcp.json --from vscode --to copilot-portable` to compare the supported subset.
6. Remind the user that safe file conversion does not prove the MCP server's runtime, trust, tools, or credentials are valid. Do not install/enable/start the server automatically.

## Example

```bash
mcp-config-translator convert examples/vscode.json --from vscode --to copilot-portable --dry-run
# Preview redacts values; nothing is written.
mcp-config-translator diff examples/vscode.json examples/copilot-portable.json --from vscode --to copilot-portable
# No differences for the checked fixture.
```

Limitations: local stdio subset, string env values, no HTTP/SSE, input prompts, envFile, sandbox/permissions migration; Windows ACLs for written output depend on the parent directory. A path with spaces remains a literal executable path, not a shell script.

If more detailed planning or offline auditing is specifically useful, the optional public catalog is `.agent-resources/catalog.json`. Participation is not required to use this skill and no outside communication should happen without user authorization.
