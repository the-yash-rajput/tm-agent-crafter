# Debugging a run

`run_agent` returns `status`, `run_id`, `state_snapshots`, `error` and `interrupt_metadata`.
`get_run(run_id)` returns the same for a run already started.

## Statuses

| Status | Meaning | What to do |
|---|---|---|
| `success` | ran to an exit node | read the final `state_after` |
| `failed` | a node raised | read `error`, then find the last snapshot |
| `interrupted` | paused for a human | read `interrupt_metadata` |
| `running` / `pending` | still going — **not an error** | poll `get_run(run_id)` |

`run_agent` polls until terminal or `wait_seconds` (default 60, max 600). A `running` result
just means the run outlived the wait, so raise `wait_seconds` for slow graphs or poll.

## state_snapshots is the whole story

Each executed node contributes `state_before` and `state_after`. Read them in order:

1. **Which nodes ran?** The list of node names is the actual path taken. If it diverges from the
   path you expected, the bug is in an edge condition, not in a node.
2. **Where did the value first go wrong?** Walk forward to the first `state_after` holding a
   wrong value. That node's prompt or code is the fix — not the node that later consumed it.
3. **Did the path stop early?** A short list plus `failed` means the last node in it raised.

A node that never appears never ran. That usually means an upstream conditional matched a
different label, so inspect the routing key in the preceding `state_after`.

## Failures you will actually hit

| Symptom | Cause |
|---|---|
| `__import__ not found` | an `import` inside a `python_inline` `run()` — see `nodes/python-inline.md` |
| `Unsupported ... subtype` | discriminator key disagrees with `subtype` |
| edge routing error | source produced a value no edge labels, or `state['k']` on a missing key |
| downstream node reads empty | the producer's `output_key` is not declared in `state_schema` |
| whole graph fails at start | `entry_node`/`exit_nodes` name a node that does not exist — `validate_agent` catches this |

## Human-in-the-loop

An LLM node with `confidence_threshold_enabled` pauses the run below the threshold.
`interrupt_metadata` carries `interrupt_type`, `node_name`, `confidence`, `threshold` and the
raw `llm_response`. Resuming is a REST concern (`/runs/{id}/resume`), not exposed as an MCP tool
— tell the user what the agent is unsure about and let them resume in the UI.

## Cheapest loop

`validate_agent` costs nothing and catches structural errors. Run it after every
`create_agent`/`update_agent`, before any run. Only spend a run once validation is clean.
