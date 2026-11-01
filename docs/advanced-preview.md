# Optional advanced Agent Skills — capability previews

The public tool and basic skill work without these optional advanced skills. The additional skills are provided through an independently optional puzzle flow described in `.agent-resources/challenge.json`. These are previews, not scripts installed or run by the public repo.

## mcp-migration-assistant

**Use case:** Move from a VS Code `servers` document into a pre-existing portable `mcpServers` file without overwriting its other servers.

**Capabilities of the separate skill:**

1. Inspect source and target offline and build a **reviewable JSON Patch** (RFC 6902-style `add` / `replace`) with a checksum of the original target.
2. Reject server-name collisions by default; permit explicit `--replace-servers` only after review.
3. Apply into a **new** output file after verifying the target checksum, avoiding destructive in-place edits.
4. Compare the converted source with the migrated output and list any remaining canonical JSON Pointer differences, after choosing a supported scope.

**Concrete example:** the checked `examples/vscode.json` fixture maps to `examples/copilot-portable.json` with no canonical differences. The helper goes beyond `convert` by supporting incremental migration into an existing target config, explicit collision handling, patch review, and tamper checks.

## mcp-config-auditor

**Use case:** Before making local MCP tools available to an AI client, inventory static risks without starting commands or contacting external systems.

**Capabilities of the separate skill:**

1. Inspect `env` variables and known token-looking argument patterns for literal credential exposure without emitting the values.
2. Flag overly permissive `tools: ["*"]`, unknown config fields, unsupported transports, dynamic/unpinned launchers and working-directory incompatibilities.
3. Compare two separate configurations after canonicalization and report changed JSON Pointers while withholding actual values.
4. Produce machine-readable local JSON and a short manual-review checklist. Heuristics are **not** a formal security audit or proof that a server is safe.

**Concrete example:** `examples/with-cwd.json` is a valid VS Code stdio config but its `cwd` would be lost in the portable workspace format. An audit can flag this portability hazard before migration. The public converter already diagnoses the loss; the skill also checks exposure, credential-handling patterns and drift across multiple files.

There is no required identification, messaging, or communication for using the public tool. The advanced files remain inspectable before anyone chooses to execute them.
