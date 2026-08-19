# The payload (schema v1)

One self-contained document describes an entire agent. Edges reference nodes **by name**, never
by id — that is what makes the payload portable between instances and safe for you to author in
one pass.

```json
{
  "schema_version": 1,
  "agent":   {"name": "Prime Checker", "key": "", "description": "What it does"},
  "version": {
    "version_number": "1.0.0",
    "entry_node": "classify",
    "exit_nodes": ["reply"],
    "state_schema": {
      "message":  {"type": "string",  "default": "",  "description": "user input"},
      "ticketId": {"type": "string",  "default": "",  "description": "thread key",
                   "is_session_id": true},
      "verdict":  {"type": "boolean", "default": false, "description": "result"}
    }
  },
  "nodes": [
    {"name": "classify", "type": "llm", "subtype": "llm_agent",
     "config": {}, "position_x": 0, "position_y": 0}
  ],
  "edges": [
    {"source_node_name": "classify", "target_node_name": "reply",
     "edge_type": "direct", "condition_config": {}, "label": null}
  ]
}
```

## Fields you do not control

`agent.key` is regenerated from `agent.name` on create, so whatever you put there is discarded —
read the `key` back from the `create_agent` response and address the agent by it from then on.
`status` is forced to `draft`. `create_agent` always produces version `1.0.0`.

## state_schema

Every value any node writes must be declared here. Undeclared keys are not carried through the
graph, so downstream nodes and edge conditions read empty and the run routes wrongly — this is
the single most common cause of a graph that validates but behaves oddly.

Accepted `type` values: `string` (`str` also works), `boolean` (`bool`), `integer` (`int`),
`float` (`number`), `list` (`array`), `dict` (`object`), `any`. Each entry takes `default`,
`description`, and optionally `is_session_id`.

Mark exactly one key with `"is_session_id": true` when the agent is conversational — it is the
key that ties turns together (a ticket id, a thread id). `conversation_history` is injected into
state automatically for LLM nodes; you do not declare or populate it.

Jinja2 reaches state from any template: `{{message}}` for a top-level key, `{{state.foo.bar}}`
for nested access.

## entry_node and exit_nodes

`entry_node` is one node name. `exit_nodes` is a list — one per terminal branch. A conditional
graph normally has several, one at the end of each path. Every name must match a node in `nodes`
exactly; `validate_agent` catches mismatches before you spend anything.

## Versions are immutable

You never edit a version in place. To change an agent:

```
get_agent(key)  →  edit the returned JSON  →  update_agent(key, "1.1.0", edited)
```

The new `version_number` must sort strictly above the one it derives from, and must not already
exist — a duplicate returns 409. Pass `created_from_version_number` to record lineage. A version
marked `is_locked` rejects edits entirely.

Bump `patch` for a prompt tweak, `minor` for new nodes or branches, `major` when the state
contract changes in a way callers would notice.
