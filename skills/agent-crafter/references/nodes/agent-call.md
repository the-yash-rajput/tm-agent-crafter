# `functional` / `agent_call`

Invokes another Agent Crafter agent as a sub-graph and waits for it. Use it to factor a large
workflow into reusable pieces, or to call an agent someone else maintains. It is hidden from the
frontend palette (`show_in_frontend: false`), so it only turns up in payloads.

```json
{"node_type": "functional", "function_type": "agent_call",
 "agent_call": {
   "target_agent_key": "payout_classification_agent",
   "target_agent_id": "",
   "target_agent_name": "",
   "input_mode": "template",
   "input_key": "",
   "input_template": "{\"message\": {{message | tojson}}, \"ticketId\": {{state.ticketId | tojson}}}",
   "output_mode": "write_to_key",
   "output_key": "classification_result",
   "include_run_metadata": true}}
```

Identify the target by **one** of `target_agent_key` (preferred — stable and readable),
`target_agent_id`, or `target_agent_name`. Leave the others empty. An agent cannot call itself.

## Input modes

| `input_mode` | The child starts with |
|---|---|
| `entire_state` | the caller's whole state |
| `state_key` | `state[input_key]`, which must be a dict |
| `template` | the rendered `input_template` (Jinja2, must render to a JSON object) |

The caller's `session_id` and `conversation_history` are added automatically, so the child's LLM
nodes see the conversation.

## Output modes: `merge_state` replaces, it does not merge

The child's output is **its final state**, meaning the exit node's `state_after`.

| `output_mode` | Caller's state afterwards |
|---|---|
| `write_to_key` | the caller's state, plus the child's final state under `output_key` |
| `merge_state` (the default when omitted) | **the child's final state, and nothing else** |

`merge_state` is only safe with `input_mode: "entire_state"`, where the child started from the
caller's whole state and so normally hands it all back. With `state_key` or `template` input,
`merge_state` drops every caller key the child never saw: `message`, earlier node outputs, and
everything else. **Use `write_to_key` unless you have a reason not to.** It also keeps the two
agents' key names from colliding.

`include_run_metadata: true` adds a second key, `<output_key>_meta`, holding
`{target_agent_id, target_agent_key, target_agent_name, run_id, status}`. Keep it: the child's
`run_id` is the way into its own `state_snapshots` when the child misbehaves. A child that
*raises* fails the caller's run with the child's error.

## Where it cannot go

The target must not contain a `wait` node, at any depth. A sub-run has no caller left to answer
when it wakes. `validate_agent` rejects a direct call into a wait-containing agent, and a deeper
one fails at run time.

## Recursion limit

Nesting is capped at **8** levels (`GraphRunner.max_agent_call_depth`). Cycles are possible if
two agents call each other; the depth cap turns that into a failed run rather than a hang, but
the graph is still wrong.

## Worked example: reuse a shared classifier

`payout_classification_agent` is maintained by another team. Its exit node leaves
`{"message": …, "ticketId": …, "classification": {"category": "refund", "confidence": 0.91}}`
in its state. Called with the config above, from a caller whose state holds
`message: "where is my refund for T-1001"`, `ticketId: "T-1001"` and `mis_result: {…}`:

```json
{"message": "where is my refund for T-1001", "ticketId": "T-1001", "mis_result": {"…": "…"},
 "classification_result": {"message": "where is my refund for T-1001", "ticketId": "T-1001",
                           "classification": {"category": "refund", "confidence": 0.91}},
 "classification_result_meta": {"target_agent_key": "payout_classification_agent",
                                "run_id": 4630, "status": "success", "…": "…"}}
```

Route on it with `state.get('classification_result', {}).get('classification', {}).get('category') == 'refund'`
and its exact negation. The same call with `output_mode: "merge_state"` would leave only the
child's three keys, and `mis_result` would be gone.
