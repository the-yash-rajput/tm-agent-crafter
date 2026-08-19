# `functional` / `agent_call`

Invokes another Agent Crafter agent as a sub-graph. Use it to factor a large workflow into
reusable pieces, or to call an agent someone else maintains.

```json
{"node_type": "functional", "function_type": "agent_call",
 "agent_call": {
   "target_agent_key": "payout_classification_agent",
   "target_agent_id": "",
   "target_agent_name": "",
   "input_mode": "entire_state",
   "input_key": "",
   "input_template": "{\n  \"input\": \"{{message}}\"\n}",
   "output_mode": "merge_state",
   "output_key": "agent_result",
   "include_run_metadata": true}}
```

Identify the target by **one** of `target_agent_key` (preferred — stable and readable),
`target_agent_id`, or `target_agent_name`. Leave the others empty.

## Input modes

| `input_mode` | Sends |
|---|---|
| `entire_state` | the whole state dict |
| `state_key` | just `state[input_key]` |
| `template` | the rendered `input_template` (Jinja2, must produce valid JSON) |

Prefer `state_key` or `template` over `entire_state` — passing everything couples the two agents
to each other's full state shape, so a rename in either one breaks the pair.

## Output modes

`merge_state` folds the sub-agent's state into the caller's; `write_to_key` nests it under
`output_key`. `write_to_key` is safer: `merge_state` lets the child silently overwrite a caller
key of the same name, which is painful to spot in `state_snapshots`.

`include_run_metadata` adds the child's `run_id` and `status`, which is worth keeping — it is how
you tell "the child failed" apart from "the child returned nothing".

## Recursion limit

Nesting is capped at **8** levels (`GraphRunner.max_agent_call_depth`). Cycles are possible if
two agents call each other; the depth cap turns that into a failed run rather than a hang, but
the graph is still wrong.
