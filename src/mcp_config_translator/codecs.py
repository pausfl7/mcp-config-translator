"""Verified subsets of VS Code MCP and portable Copilot project config.

References: https://code.visualstudio.com/docs/agents/reference/mcp-configuration
            https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers
No command is ever launched and no shell lexer is used.
"""
from __future__ import annotations
import re
from typing import Any
from .model import Config, Issue, Server, pointer

SUPPORTED = ("vscode", "copilot-portable")

_ENV_TOKEN = re.compile(r"\$\{([^{}]+)\}")
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_SHELL_INLINE = re.compile(r"^(?:(?:python(?:3(?:\.\d+)?)?|py|node|npx|npm|uv|uvx|bun|docker|cmd|bash|sh|pwsh|powershell)(?:\.exe)?)\s+[-/'\"]", re.I)
_SHELL_OPERATORS = re.compile(r"(?:\s(?:&&|\|\||[|;><])\s|[`\r\n])")


def normalize_dialect(name: str) -> str:
    if name not in SUPPORTED:
        raise ValueError("unknown dialect")
    return name


def _value_path(parts: list[str]) -> str:
    return pointer(parts)


def _issue(issues: list[Issue], code: str, parts: list[str], detail: str, severity: str = "loss") -> None:
    issues.append(Issue(code, _value_path(parts), detail, severity))


def _translate_tokens(value: str, source: str, target: str, issues: list[Issue], loc: list[str]) -> str:
    """Translate documented references; unrepresentable macros are fatal, not silently literalized."""
    if source == target:
        return value

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if source == "vscode" and target == "copilot-portable":
            if token.startswith("env:") and _NAME.fullmatch(token[4:]):
                return "${" + token[4:] + "}"
            _issue(issues, "unsupported-reference", loc,
                   "VS Code placeholder has no verified portable equivalent; rewrite it manually", "error")
            return match.group(0)
        if source == "copilot-portable" and target == "vscode":
            if _NAME.fullmatch(token):
                return "${env:" + token + "}"
            _issue(issues, "unsupported-reference", loc,
                   "Portable placeholder/default cannot be represented by VS Code env syntax", "error")
            return match.group(0)
        raise AssertionError("unexpected format")
    return _ENV_TOKEN.sub(replace, value)


def _string(val: Any, issues: list[Issue], loc: list[str], field: str) -> str | None:
    if not isinstance(val, str) or not val:
        _issue(issues, "invalid-field", loc, field + " must be a nonempty string", "error")
        return None
    return val


def parse(doc: Any, dialect: str, *, target: str | None = None) -> Config:
    """Parse a strict stdio subset. Extra data yields a loss report; no silent omission."""
    src = normalize_dialect(dialect)
    dst = normalize_dialect(target) if target is not None else src
    issues: list[Issue] = []
    result = Config(issues=issues)
    if not isinstance(doc, dict):
        _issue(issues, "invalid-root", [], "top-level JSON object required", "error")
        return result
    top = "servers" if src == "vscode" else "mcpServers"
    for key in sorted(doc):
        if key != top:
            _issue(issues, "unsupported-top-level-key" if key in {"inputs", "sandbox"} else "unknown-top-level-key", [key], "top-level key is outside the supported subset")
    if top not in doc or not isinstance(doc[top], dict):
        _issue(issues, "invalid-servers", [top], "required object of MCP server definitions", "error")
        return result
    for name, raw in sorted(doc[top].items()):
        base = [top, str(name)]
        if not isinstance(name, str) or not name:
            _issue(issues, "invalid-server-name", base, "nonempty server name required", "error")
            continue
        if not isinstance(raw, dict):
            _issue(issues, "invalid-server", base, "server must be an object", "error")
            continue
        kind = raw.get("type")
        expected_type = "stdio" if src == "vscode" else "local"
        valid_types = (None, "local") if src == "copilot-portable" else ("stdio",)
        if kind not in valid_types or ("type" in raw and kind is None) or "url" in raw:
            _issue(issues, "unsupported-transport", base + ["type"],
                   "only local stdio command servers are supported", "error")
            continue
        cmd = _string(raw.get("command"), issues, base + ["command"], "command")
        if cmd is None:
            continue
        if _SHELL_INLINE.search(cmd) or _SHELL_OPERATORS.search(cmd) or re.search(r"\.(?:exe|py|js|sh|cmd|bat)\s+[-/]", cmd, re.I) or "\"" in cmd or "'" in cmd:
            _issue(issues, "ambiguous-command", base + ["command"],
                   "command appears to include shell syntax/arguments; put only the executable in command and split arguments into args[]", "error")
        args_value = raw.get("args", [])
        args: list[str] = []
        if not isinstance(args_value, list) or any(not isinstance(a, str) for a in args_value):
            _issue(issues, "invalid-args", base + ["args"], "args must be a JSON array of strings; no shell tokenization", "error")
        else:
            args = list(args_value)
        env_value = raw.get("env", {})
        env: dict[str, str] = {}
        if not isinstance(env_value, dict):
            _issue(issues, "invalid-env", base + ["env"], "env must be an object of string values in this subset", "error")
        else:
            for key, value in sorted(env_value.items()):
                if not isinstance(key, str) or not _NAME.fullmatch(key) or not isinstance(value, str):
                    _issue(issues, "invalid-env-entry", base + ["env", str(key)],
                           "environment names must be identifiers and values strings", "error")
                else:
                    env[key] = _translate_tokens(value, src, dst, issues, base + ["env", key])
        cwd = raw.get("cwd")
        if "cwd" in raw and (not isinstance(cwd, str) or not cwd):
            _issue(issues, "invalid-cwd", base + ["cwd"], "cwd must be a nonempty string", "error")
            cwd = None
        if "cwd" in raw and src == "copilot-portable":
            _issue(issues, "unsupported-source-cwd", base + ["cwd"],
                   "workspace-root portable .mcp.json does not document cwd support", "loss")
            cwd = None
        if cwd is not None and dst == "copilot-portable":
            _issue(issues, "dropped-cwd", base + ["cwd"],
                   "working directory is not supported in workspace-root portable .mcp.json")
            cwd = None
        allowed = {"command", "args", "env", "cwd", "type"}
        for key in sorted(set(raw) - allowed):
            code = "unsupported-server-key" if key in {"sandbox", "sandboxEnabled", "tools", "envFile", "dev", "headers", "timeout"} else "unknown-server-key"
            _issue(issues, code, base + [key],
                   "unsupported server property cannot be safely represented")
        if kind is None and src == "vscode":
            _issue(issues, "missing-type", base + ["type"],
                   "VS Code stdio entries require type: stdio", "error")
        args = [_translate_tokens(x, src, dst, issues, base + ["args", str(i)]) for i, x in enumerate(args)]
        cmd = _translate_tokens(cmd, src, dst, issues, base + ["command"])
        if isinstance(cwd, str):
            cwd = _translate_tokens(cwd, src, dst, issues, base + ["cwd"])
        result.servers[name] = Server(cmd, args, env, cwd, "args" in raw, "env" in raw)
    return result


def render(config: Config, dialect: str) -> dict[str, Any]:
    dst = normalize_dialect(dialect)
    outer = "servers" if dst == "vscode" else "mcpServers"
    rendered: dict[str, Any] = {}
    for name, s in sorted(config.servers.items()):
        raw: dict[str, Any] = {}
        if dst == "vscode":
            raw["type"] = "stdio"
        raw["command"] = s.command
        if s.has_args:
            raw["args"] = list(s.args)
        if s.has_env:
            raw["env"] = dict(sorted(s.env.items()))
        if s.cwd is not None and dst == "vscode":
            raw["cwd"] = s.cwd
        rendered[name] = raw
    return {outer: rendered}
