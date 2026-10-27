#!/usr/bin/env python3
"""stdio -> HTTP MCP proxy that always talks to the *active* Agent Crafter workspace.

Claude Code runs this as the plugin's MCP server. Each JSON-RPC line from stdin is POSTed to
<host>/api/agent-crafter/mcp of whatever workspace is active in workspaces.json right now (see
crafter_workspace.py), falling back to CRAFTER_HOST / CRAFTER_API_KEY from the install prompt.
When the active workspace changes, the cached `initialize` is replayed against the new host,
so `/crafter-workspace <name>` switches mid-session with no restart.

`crafter_proxy.py --selftest` checks the response parser.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

import crafter_workspace

MCP_PATH = "/api/agent-crafter/mcp"
TIMEOUT_S = 600  # run_agent waits on real LLM calls
# Claude Code gives up on a server whose initialize takes ~30s, and then shows only "-32000".
# Failing sooner lets the real reason (host unreachable, VPN off) reach the log and the error.
CONNECT_TIMEOUT_S = 5  # per socket step; a dead host takes ~2x this in all


def log(msg: str) -> None:
    print(f"[crafter-proxy] {msg}", file=sys.stderr, flush=True)


def target() -> tuple[str, str, str] | None:
    ws = crafter_workspace.active()
    if ws:
        return ws
    host, key = os.environ.get("CRAFTER_HOST", ""), os.environ.get("CRAFTER_API_KEY", "")
    if host and key and "${" not in host + key:  # unset userConfig may arrive unexpanded
        return ("install-time host", host.rstrip("/"), key)
    return None


def parse_body(content_type: str, body: str) -> list[dict]:
    """A POST answers with either plain JSON or an SSE stream of JSON-RPC messages."""
    if not body.strip():
        return []
    if "text/event-stream" not in content_type:
        msg = json.loads(body)
        return msg if isinstance(msg, list) else [msg]
    out = []
    for event in body.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in event.split("\n") if line.startswith("data:"))
        if data:
            out.append(json.loads(data))
    return out


class Proxy:
    def __init__(self) -> None:
        self.init_msg: dict | None = None  # the client's initialize, replayed on a switch
        self.connected: tuple[str, str] | None = None  # (host, key) the session belongs to
        self.session_id: str | None = None
        self.protocol: str | None = None

    def post(self, host: str, key: str, msg: dict, timeout: float = TIMEOUT_S) -> list[dict]:
        headers = {
            "Authorization": f"ApiKey {key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.protocol:
            headers["MCP-Protocol-Version"] = self.protocol
        req = urllib.request.Request(host + MCP_PATH, json.dumps(msg).encode(), headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            self.session_id = resp.headers.get("Mcp-Session-Id") or self.session_id
            return parse_body(resp.headers.get("Content-Type", ""), resp.read().decode())

    def initialize(self, host: str, key: str) -> list[dict]:
        self.session_id = self.protocol = None
        replies = self.post(host, key, self.init_msg, CONNECT_TIMEOUT_S)
        self.protocol = next((r["result"].get("protocolVersion") for r in replies if "result" in r), None)
        self.connected = (host, key)
        return replies

    def connect(self, host: str, key: str) -> None:
        """Open a fresh session on host by replaying the client's initialize."""
        self.initialize(host, key)
        self.post(host, key, {"jsonrpc": "2.0", "method": "notifications/initialized"}, CONNECT_TIMEOUT_S)

    def handle(self, msg: dict) -> list[dict]:
        ws = target()
        if not ws:
            raise RuntimeError("No Agent Crafter workspace. Add one: /crafter-workspace add <url> <key> [name]")
        name, host, key = ws
        try:
            if msg.get("method") == "initialize":
                self.init_msg = msg
                return self.initialize(host, key)
            if msg.get("method") == "notifications/initialized" and self.connected == (host, key):
                return self.post(host, key, msg)
            if self.connected != (host, key) and self.init_msg:
                log(f"switching to workspace '{name}' ({host})")
                self.connect(host, key)
            try:
                return self.post(host, key, msg)
            except urllib.error.HTTPError as e:
                if e.code != 404 or not self.init_msg:
                    raise
                log("session expired, reconnecting")  # backend restarted
                self.connect(host, key)
                return self.post(host, key, msg)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            raise RuntimeError(f"Workspace '{name}' ({host}) returned HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError(f"Workspace '{name}' ({host}) unreachable: {e}. On VPN? Switch with /crafter-workspace <name>.") from e


def main() -> None:
    proxy = Proxy()
    # ponytail: one request at a time; parallel tool calls queue behind a slow run_agent.
    # Thread per request (with a lock around connect) if that ever hurts.
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        try:
            replies = proxy.handle(msg)
        except (RuntimeError, ValueError) as e:
            log(str(e))
            replies = [{"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32000, "message": str(e)}}] if "id" in msg else []
        for r in replies:
            sys.stdout.write(json.dumps(r) + "\n")
        sys.stdout.flush()


def selftest() -> None:
    assert parse_body("application/json", '{"id":1,"result":{}}') == [{"id": 1, "result": {}}]
    assert parse_body("application/json", "") == []
    sse = 'event: message\r\ndata: {"id":1,\r\ndata: "result":{}}\r\n\r\nid: 2\ndata: {"id":2}\n\n'
    assert parse_body("text/event-stream; charset=utf-8", sse) == [{"id": 1, "result": {}}, {"id": 2}]
    assert crafter_workspace.default_name("http://localhost:7002") == "localhost"
    assert crafter_workspace.default_name("https://drm-staging.x.com") == "drm-staging"
    assert crafter_workspace.mask("drm_pub_abc.drm_sk_secret") == "drm_pub_abc.****"
    print("ok")


if __name__ == "__main__":
    selftest() if sys.argv[1:] == ["--selftest"] else main()
