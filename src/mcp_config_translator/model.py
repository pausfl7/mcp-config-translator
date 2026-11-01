"""Narrow canonical model; deliberate refusal to invent unsupported semantics."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    detail: str
    severity: str = "loss"  # loss (explicit opt-in allowed) or error (cannot translate)

    def as_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "code": self.code, "path": self.path, "detail": self.detail}


@dataclass
class Server:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    # Keep track of which optional fields were present; preserve absent vs empty on round-trip.
    has_args: bool = False
    has_env: bool = False


@dataclass
class Config:
    servers: dict[str, Server] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def canonical(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, s in sorted(self.servers.items()):
            entry: dict[str, Any] = {"command": s.command}
            if s.has_args:
                entry["args"] = list(s.args)
            if s.has_env:
                entry["env"] = dict(sorted(s.env.items()))
            if s.cwd is not None:
                entry["cwd"] = s.cwd
            result[name] = entry
        return {"servers": result}


def pointer(parts: list[str]) -> str:
    return "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1") for x in parts)


def mismatch_pointers(left: Any, right: Any, prefix: list[str] | None = None) -> list[str]:
    """Leaf-level JSON Pointer differences; expose paths only, never values."""
    base = [] if prefix is None else prefix
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                result.append(pointer(base + [key]))
            else:
                result.extend(mismatch_pointers(left[key], right[key], base + [key]))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for i in range(max(len(left), len(right))):
            if i >= len(left) or i >= len(right):
                result.append(pointer(base + [str(i)]))
            else:
                result.extend(mismatch_pointers(left[i], right[i], base + [str(i)]))
        return result
    return [] if type(left) is type(right) and left == right else [pointer(base)]
