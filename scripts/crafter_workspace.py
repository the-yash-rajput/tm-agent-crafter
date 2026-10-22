#!/usr/bin/env python3
"""Manage Agent Crafter workspaces: named host + API key pairs, one of them active.

Usage:
  crafter_workspace.py list
  crafter_workspace.py use <name>
  crafter_workspace.py add <url> [name]     # key on stdin, or a hidden prompt on a TTY
  crafter_workspace.py remove <name>

The file lives at ~/.config/tm-agent-crafter/workspaces.json (mode 600). crafter_proxy.py
re-reads it on every request, so `use` takes effect on the next tool call.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import sys
import tempfile
from urllib.parse import urlparse

PATH = os.path.join(os.path.expanduser("~"), ".config", "tm-agent-crafter", "workspaces.json")
KEY_RE = re.compile(r"^drm_pub_\S+\.drm_sk_\S+$")


def load() -> dict:
    try:
        with open(PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"active": None, "workspaces": {}}
    data.setdefault("workspaces", {})
    data.setdefault("active", None)
    return data


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(PATH), mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(PATH))  # mkstemp creates it 0600
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, PATH)


def active() -> tuple[str, str, str] | None:
    """(name, host, api_key) of the active workspace, or None when there is none."""
    data = load()
    ws = data["workspaces"].get(data["active"] or "")
    return (data["active"], ws["host"], ws["api_key"]) if ws else None


def mask(key: str) -> str:
    return key.split(".", 1)[0] + ".****"


def default_name(url: str) -> str:
    # localhost:7002 -> localhost, drm-staging.x.com -> drm-staging
    return (urlparse(url).hostname or "workspace").split(".")[0]


def cmd_list(data: dict) -> None:
    if not data["workspaces"]:
        print("No workspaces. Add one: /crafter-workspace add <url> <key> [name]")
        return
    for name, ws in data["workspaces"].items():
        mark = "*" if name == data["active"] else " "
        print(f"{mark} {name:<16} {ws['host']:<40} {mask(ws['api_key'])}")


def main(argv: list[str]) -> int:
    data = load()
    cmd, args = (argv[0], argv[1:]) if argv else ("list", [])

    if cmd == "list":
        cmd_list(data)
    elif cmd == "use" and len(args) == 1:
        if args[0] not in data["workspaces"]:
            sys.exit(f"No workspace '{args[0]}'. Known: {', '.join(data['workspaces']) or 'none'}")
        data["active"] = args[0]
        save(data)
        print(f"Active workspace: {args[0]} ({data['workspaces'][args[0]]['host']})")
    elif cmd == "add" and 1 <= len(args) <= 2:
        url = args[0].rstrip("/")
        if not re.match(r"^https?://[^/\s]+", url):
            sys.exit(f"Not a http(s) URL: {url}")
        name = args[1] if len(args) == 2 else default_name(url)
        key = getpass.getpass(f"API key for '{name}': ") if sys.stdin.isatty() else sys.stdin.readline()
        key = key.strip()
        if not KEY_RE.match(key):
            sys.exit("API key must look like drm_pub_xxx.drm_sk_xxx")
        replaced = name in data["workspaces"]
        data["workspaces"][name] = {"host": url, "api_key": key}
        if not data["active"]:
            data["active"] = name
        save(data)
        print(f"{'Updated' if replaced else 'Added'} '{name}' -> {url} ({mask(key)}). Active: {data['active']}")
    elif cmd == "remove" and len(args) == 1:
        if data["workspaces"].pop(args[0], None) is None:
            sys.exit(f"No workspace '{args[0]}'")
        if data["active"] == args[0]:
            data["active"] = next(iter(data["workspaces"]), None)
        save(data)
        print(f"Removed '{args[0]}'. Active: {data['active'] or 'none (falls back to install-time host)'}")
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
