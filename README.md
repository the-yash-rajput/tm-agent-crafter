# TM Agent Crafter — Claude plugin

Build, validate and run Agent Crafter workflows by describing them to Claude in plain language.

Agent Crafter models an agent as a **LangGraph workflow**: a graph of typed nodes (LLM calls,
sandboxed Python, HTTP, RAG, Kafka/RabbitMQ publishes, timed waits, document classification and extraction)
wired together by direct and conditional edges. This plugin gives Claude the node catalog, the
payload schema and the debugging playbook, so you can say what you want the agent to do and
Claude authors, validates, runs and iterates on the graph for you.

## Requirements

This plugin is a client. It talks to an **Agent Crafter backend** over MCP, and does nothing on
its own — you need a reachable instance before installing.

## Install

```
/plugin marketplace add the-yash-rajput/tm-agent-crafter
/plugin install tm-agent-crafter
```

To try it locally without installing:

```
claude --plugin-dir /path/to/tm-agent-crafter
```

Claude Code then prompts for two values, stored per-user and never committed:

| Field | Value |
|---|---|
| **Agent Crafter host** | Base URL of your instance, no trailing slash — e.g. `http://localhost:7001` |
| **API key** | `drm_pub_….drm_sk_…` |

Issue a key in the backend's Django admin → **API Keys** → Add. The secret is shown once, on the
reveal screen, and is never recoverable afterwards. Revoke by unticking `is_active`.

> API keys are global-scope: any valid key can read and write **every** agent on that instance.
> Use a separate key per person so you can revoke one without disrupting others.

## Use

Just describe what you want:

> Build me an agent that takes a claim document, classifies it, and files a support ticket if
> it's a missing policy copy.

Claude plans the graph with you first — nodes have real side effects, so it confirms the shape
before building. Then it reads the node catalog, authors the payload, validates it, runs it, and
iterates on failures using the per-node state snapshots. Ask it to "show me the agent" or "add a
retry branch" to keep editing; each change lands as a new immutable version.

## What's included

A single skill, `agent-crafter`, with progressive-disclosure reference files:

| Reading | File |
|---|---|
| Payload envelope, `state_schema`, versioning, key/name rules | `references/payload.md` |
| `direct` vs `conditional` edges, branch coverage | `references/edges.md` |
| Diagnosing a failed or wrong run | `references/debugging.md` |
| Finding, reading and writing the shared agent library | `references/library.md` |

Plus one file per node type under `references/nodes/` — `llm-chat`, `llm-agent`, `data-collection`,
`python-inline`, `agent-call`, `rag`, `wait`, `api`, `rabbitmq`, `kafka`, `document-classification`,
`document-extraction`.

The plugin also declares an MCP server (`.mcp.json`) pointing at
`<host>/api/agent-crafter/mcp`, authenticated with your API key.

## Agent library (optional)

If you have the Google Drive connector enabled, Claude keeps a library of working agents in a
Drive folder named **`Agent Crafter - Agents`** — it reads existing agents there as reference
patterns before authoring, and writes each new agent back, so the library compounds as you use
it.

The folder is resolved **by name, never by a hardcoded id**, so every user gets their own. Keep
exactly one folder with that name visible to your account; if two match, Claude stops and asks.

A caveat worth knowing: listing a link-shared folder owned by a *different* Google account
returns nothing at all through the Drive API, so the folder can look empty while holding
everything. If that happens, add a shortcut to it in your own Drive (right-click → *Organise* →
*Add shortcut to Drive*) so the name lookup resolves, or paste the folder link into the chat to
override the lookup for that conversation.

> Agent payloads embed whatever the graph contains: system prompts, internal hostnames,
> config-key names and routing ids. Treat the library with the same care as the agents
> themselves, and keep it scoped to people who should see it.

## Troubleshooting

If the tools don't appear, run `/mcp` first — it says whether the server was skipped outright,
failed to connect, or connected with zero tools. Each points somewhere different:

| `/mcp` shows | Cause | Fix |
|---|---|---|
| `tm-agent-crafter` absent, or a `"url" but no "type"` error | Plugin config is malformed | Update to v0.1.1 or later — v0.1.0 omitted `"type": "http"`, so Claude Code read the entry as a stdio server and skipped it |
| Connection failure / 404 | Backend doesn't serve the MCP route | The deployment predates the `/api/agent-crafter/mcp` mount — check with the probe below |
| Connected, but tools error on auth | Key revoked or wrong host | Re-issue in Django admin → API Keys; confirm the host has no trailing slash |

Probe the backend directly — a 200 means the route is live:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$HOST/api/agent-crafter/mcp" \
  -H "Authorization: ApiKey $KEY" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
```

A 404 here with `/api/health_check` returning 200 means the host is fine and only the MCP mount
is missing.

## License

MIT — see [LICENSE](./LICENSE).
