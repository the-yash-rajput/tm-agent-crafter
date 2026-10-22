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

**Keep it small. Do not declare every key the graph uses.** State is an open dict: whatever a
node writes to its `output_key` is visible to every later node and edge condition without being
listed here. `state_schema` only seeds **default values** before the first node runs.

Declare a key only when:

- it needs a default — a node or edge reads it before anything has written it (e.g. a counter,
  a flag an edge checks on the first turn, a list a node appends to);
- it is a key you want carried from run 1 → run 2 → run 3 within a session and it must exist,
  with a sane value, on run 1 (later turns are seeded from an earlier run, below; the schema
  covers the first one);
- it is the `is_session_id` key.

Everything else — node outputs, intermediate values — stays out.

### How a later turn is seeded

A new turn in a session starts from the **last snapshot `state_after` of the most recent run
(by start time) that succeeded or is parked on a `wait`**, minus `session_id`,
`conversation_history` and `file_details`. On top of that, the new turn's `message`, `metadata`
and `files` win, and `state_schema` defaults fill only the keys that are still missing. So a
default never overwrites a value carried from an earlier turn.

Failed runs, runs still executing, and runs paused for any reason other than a wait are skipped,
so seeding falls back to the run before them. A value written by a turn that later failed is
**not** carried forward. The interplay with waits, including superseded runs and the race when
a message arrives before a run parks, is in `nodes/wait.md`.

Accepted `type` values: `string` (`str` also works), `boolean` (`bool`), `integer` (`int`),
`float` (`number`), `list` (`array`), `dict` (`object`), `any`. Each entry takes `default`,
`description`, and optionally `is_session_id`.

Mark exactly one key with `"is_session_id": true` when the agent is conversational — it is the
key that ties turns together (a ticket id, a thread id). `conversation_history` is injected into
state automatically for LLM nodes; you do not declare or populate it.

Jinja2 reaches state from any template, but only through two names: `{{message}}`, and
`{{state.<key>}}` for everything else (`{{state.foo.bar}}` for nested access). A bare
`{{policy_number}}` renders empty without an error.

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

### Large payloads: import from a file

`update_agent` takes the whole payload inline, so a big agent (hundreds of KB of node code)
cannot go through it. Use the backend import route from a file instead. It follows the same rules
(a strictly higher semver, no duplicates, lineage through `from`):

```
bash ${CLAUDE_PLUGIN_ROOT}/scripts/import_version.sh <key> <new_version> <from_version> <payload.json>
```

It POSTs `{version_number, created_from_version_number, payload}` to
`<host>/api/agent-crafter/agents/<key>/versions/import` with `Authorization: ApiKey`, and sets
`payload.version.version_number` to `<new_version>`. It needs `CRAFTER_HOST` and
`CRAFTER_API_KEY` in the environment (the same key as the plugin config, and the same host
when deployed; locally it is the REST port `:7001`, not the MCP port `:7002`). Without them
it exits 2, so ask the user to set them, e.g. `! export CRAFTER_HOST=… CRAFTER_API_KEY=…`. Then
`validate_agent(key, <new_version>)` as usual.
