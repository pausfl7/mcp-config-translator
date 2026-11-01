"""CLI uses stdlib only. Never starts a server or contacts the network."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any
from .codecs import SUPPORTED, parse, render
from .model import Issue, mismatch_pointers, pointer

MAX_BYTES = 1024 * 1024
USAGE = 2
DIAGNOSTIC = 3
_SAFE_ARG = re.compile(r"(?:-{1,2}[a-zA-Z][a-zA-Z-]{0,30}|-y)\Z")
_SAFE_REF = re.compile(r"\$\{(?:env:)?[A-Za-z_][A-Za-z_0-9]*\}\Z")


class InputError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise InputError("duplicate JSON object member (refusing ambiguous configuration)")
        result[name] = value
    return result


def load_json(path: str) -> Any:
    if path == "-":
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    else:
        with open(path, "rb") as infile:
            raw = infile.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise InputError("config exceeds 1 MiB limit")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError("non-finite JSON number is forbidden")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("invalid JSON or encoding; check syntax and duplicate keys") from None


def json_string(doc: Any) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def redact(doc: Any) -> Any:
    """Deliberately conservative preview: never echo arbitrary command, arg or env values.

    A real output requires --write and is written to a new user-selected file.
    """
    if not isinstance(doc, dict):
        return "<redacted>"
    copy: dict[str, Any] = {}
    for parent, servers in doc.items():
        if parent not in ("servers", "mcpServers") or not isinstance(servers, dict):
            copy[parent] = "<redacted>"
            continue
        new: dict[str, Any] = {}
        for name, server in servers.items():
            if not isinstance(server, dict):
                new[name] = "<redacted>"
                continue
            entry: dict[str, Any] = {}
            for field, value in server.items():
                if field == "type":
                    entry[field] = value
                elif field == "env" and isinstance(value, dict):
                    entry[field] = {k: (v if isinstance(v, str) and _SAFE_REF.fullmatch(v) else "<redacted>") for k, v in value.items()}
                elif field == "args" and isinstance(value, list):
                    entry[field] = [v if isinstance(v, str) and (_SAFE_REF.fullmatch(v) or _SAFE_ARG.fullmatch(v)) else "<redacted>" for v in value]
                else:
                    entry[field] = "<redacted>"
            new[name] = entry
        copy[parent] = new
    return copy


def emit_issues(issues: list[Issue]) -> None:
    for issue in sorted(issues, key=lambda i: (i.path, i.code)):
        print(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.detail}", file=sys.stderr)


def _store_new(path: str, output: str) -> None:
    """Refuse existing paths and symlinks; permissions 0600 on POSIX."""
    destination = Path(path)
    fd, tmp = tempfile.mkstemp(dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(output)
        os.link(tmp, destination)
    finally:
        os.unlink(tmp)


def preservation(doc: dict, dialect: str, issues: list[Issue]) -> list[Issue]:
    top = "servers" if dialect == "vscode" else "mcpServers"
    blocked = {i.path for i in issues}
    rows = []
    for name, server in doc[top].items():
        for key, value in server.items():
            parts = [top, name, key]
            if pointer(parts) in blocked:
                continue
            children = list(value) if isinstance(value, dict) else range(len(value)) if isinstance(value, list) else []
            paths = [parts + [str(child)] for child in children] or [parts]
            for path in paths:
                reason = "local stdio semantics retained" if key == "type" else "retained with target reference syntax"
                rows.append(Issue("preserved", pointer(path), reason, "info"))
    return rows


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcp-config-translator",
        description="Offline stdio MCP config conversion; safe dry-run by default")
    p.add_argument("--version", action="version", version="mcp-config-translator 0.1.0")
    subs = p.add_subparsers(dest="action", required=True)
    v = subs.add_parser("validate", help="Validate documented subset and report unsupported keys")
    v.add_argument("path", help="UTF-8 JSON config file (or - for stdin)")
    v.add_argument("--from", dest="source", required=True, choices=SUPPORTED)

    c = subs.add_parser("convert", help="Preview or explicitly write translated config")
    c.add_argument("path", help="UTF-8 JSON config file (or - for stdin)")
    c.add_argument("--from", dest="source", required=True, choices=SUPPORTED)
    c.add_argument("--to", dest="target", required=True, choices=SUPPORTED)
    c.add_argument("--out", help="Destination file (only created with --write)")
    c.add_argument("--dry-run", action="store_true", help="Preview without writing (also the default)")
    c.add_argument("--write", action="store_true", help="Write complete (not redacted) config to a NEW file")
    c.add_argument("--allow-loss", action="store_true", help="Explicitly accept known loss reports for --write")

    d = subs.add_parser("diff", help="Show canonical JSON Pointer differences (no values)")
    d.add_argument("left", help="First config path")
    d.add_argument("right", help="Second config path")
    d.add_argument("--left", "--from", dest="source", required=True, choices=SUPPORTED)
    d.add_argument("--right", "--to", dest="target", required=True, choices=SUPPORTED)
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.action == "convert":
        if args.dry_run and args.write:
            print("ERROR: --dry-run and --write are mutually exclusive", file=sys.stderr)
            return USAGE
        if args.write and not args.out:
            print("ERROR: --write requires --out; stdout never contains raw config", file=sys.stderr)
            return USAGE
    try:
        if args.action == "diff":
            left = parse(load_json(args.left), args.source, target="vscode" if args.source != args.target else None)
            right = parse(load_json(args.right), args.target, target="vscode" if args.source != args.target else None)
            issues = left.issues + right.issues
            emit_issues(issues)
            if any(i.severity == "error" for i in issues):
                return DIAGNOSTIC
            paths = mismatch_pointers(left.canonical(), right.canonical())
            print(json_string({"equal": not paths, "differences": paths}), end="")
            return DIAGNOSTIC if paths or issues else 0
        target = args.target if args.action == "convert" else None
        doc = load_json(args.path)
        parsed = parse(doc, args.source, target=target)
        if args.action == "convert" and not any(i.severity == "error" for i in parsed.issues):
            emit_issues(parsed.issues + preservation(doc, args.source, parsed.issues))
        else:
            emit_issues(parsed.issues)
        if args.action == "validate":
            if parsed.issues:
                return DIAGNOSTIC
            print(f"OK: {len(parsed.servers)} stdio server(s), validated supported subset")
            return 0
        if any(i.severity == "error" for i in parsed.issues):
            print("No conversion emitted: unrepresentable input", file=sys.stderr)
            return DIAGNOSTIC
        translated = render(parsed, args.target)
        if args.write:
            if parsed.issues and not args.allow_loss:
                print("Refusing lossy write; inspect report and use --allow-loss if acceptable", file=sys.stderr)
                return DIAGNOSTIC
            _store_new(args.out, json_string(translated))
            print(f"Created {args.out} (new file, full config; treat as potentially secret-bearing)")
        else:
            print("DRY RUN: nothing written; preview values redacted")
            print(json_string(redact(translated)), end="")
        return DIAGNOSTIC if parsed.issues else 0
    except (InputError, OSError, UnicodeError) as err:
        if isinstance(err, FileExistsError):
            print("ERROR: destination exists; no overwrite performed", file=sys.stderr)
        elif isinstance(err, InputError):
            print(f"ERROR: {err}", file=sys.stderr)
        else:
            print("ERROR: input/output file could not be accessed", file=sys.stderr)
        return DIAGNOSTIC


if __name__ == "__main__":
    sys.exit(main())
