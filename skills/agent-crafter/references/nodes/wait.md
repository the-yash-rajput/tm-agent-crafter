# `functional` / `wait`

Pauses the run for a fixed duration, then resumes it automatically. Use it for a deliberate
delay inside a workflow — poll again in an hour, chase an unanswered request tomorrow, let an
upstream system settle before the next call.

```json
{"node_type": "functional", "function_type": "wait",
 "wait": {"duration_seconds": 300}}
```

That is the whole config. There is no host or callback URL here: the scheduler always calls the
backend back on its own deployment-level origin, so the callback is not a per-node choice.

`duration_seconds` must be an integer **greater than 0 and at most 2592000** (30 days). It is
validated at save time, so a bad value fails `create_agent`/`update_agent` rather than half a run
later. Past 30 days you are describing a scheduled job, not a wait — model it as one.

The node produces nothing. State passes through untouched, so there is no `output_key` and
nothing to declare in `state_schema`.

## What a paused run looks like

The run does not block a worker. It stops with `status: "interrupted"` and
`interrupt_metadata`:

```json
{"interrupt_type": "wait", "node_name": "cool_off", "duration_seconds": 300,
 "resume_at": "2026-02-01T12:05:00+05:30",
 "scheduled": true, "scheduler_task_id": 8412, "scheduler_group": "AI_AGENT_CRAFTER_WAIT"}
```

`resume_at` is when it will pick up again. This is normal and terminal for now — do not poll
`get_run` waiting for `success`, and do not re-run the agent. The state is held in the
checkpoint. Execution continues from the node after the wait as a **new run row** whose
`resumed_from_run_id` points at the parked one.

`scheduled: false` means the pause happened but nothing will wake it. `scheduler_error_kind`
says whose problem it is: `config` is a deployment fix (the backend's callback URL or scheduler
API key is unset), `payload` is a graph bug, `transport` is an outage worth retrying. The run's
state is intact either way; an operator resumes it by hand.

## A new message while the run is parked

Waits are long and customers keep talking. Two rules decide what happens. Design any agent that
contains a wait with both in mind.

### 1. The new turn starts from the state right before the wait

Every new turn in a session is seeded from **the most recent run (by start time) that either
succeeded or is parked on a wait**. That run's last snapshot `state_after` becomes the starting
state, minus the per-turn keys (`session_id`, `conversation_history`, `file_details`). The new
turn's `message`, `metadata` and `files` then override it, and `state_schema` defaults fill only
keys that are still missing.

A wait node raises *before* its own snapshot is written, so a parked run's last snapshot is
exactly the state just before the wait. Everything the run worked out up to the wait, such as
lookups, collected fields and counters, is visible to the next turn.

The parked turn's message is already in `conversation_history`, because it is appended at park
time. LLM nodes in the next run see what the customer asked first, even though that run never
replied.

| Run state | Seeds the next turn? |
|---|---|
| `success` | yes |
| `interrupted` with `interrupt_type: "wait"` | yes — the state up to the wait |
| `interrupted` for any other reason (confidence check, manual pause, crash) | no |
| `failed`, including superseded | no — seeding falls back to the run before it |
| `running` | no — a turn that is still executing is invisible to the next one |

### 2. A newer turn supersedes the parked run

When the timer fires, the parked run checks for any run in the same session that **started after
it parked**. If one exists, the parked run is never resumed. It is settled as:

```json
{"status": "failed",
 "error": "Superseded by run 4512 in the same session",
 "interrupt_metadata": {"interrupt_type": "wait", "node_name": "cool_off", "superseded_by": 4512}}
```

The scheduler gets `200 {"status": "superseded"}`, so it does not retry. No callback fires and no
reply goes out for that run. A superseded run is the system working as designed, **not a bug to
fix**, so do not re-run it.

### The timelines that follow

Three messages, and every run reaches a 3-hour wait:

| Time | Event | Result |
|---|---|---|
| t=0 | msg 1 → run A parks (timer at 3h) | |
| t=10m | msg 2 → run B, seeded from A's pre-wait state, parks (timer at 3h10m) | |
| t=20m | msg 3 → run C, seeded from B, parks (timer at 3h20m) | |
| t=3h | A wakes. B started after A parked | A → `failed`, superseded |
| t=3h10m | B wakes. C started after B parked | B → `failed`, superseded |
| t=3h20m | C wakes. Nothing newer | C resumes and finishes: **the only reply** |

Each new message restarts the clock. The customer gets one reply, 3 hours after their *last*
message, and the first request is never answered on its own.

Same start, but msg 4 takes a path with no wait:

| Time | Event | Result |
|---|---|---|
| t=0 / 10m / 20m | runs A, B, C park | |
| t=30m | msg 4 → run D, no wait on its path | D succeeds and replies at once |
| t=3h / 3h10m / 3h20m | A, B, C wake. D started after each of them parked | all three superseded |

Only D's reply goes out.

### Known gap: a message that arrives before the run parks

Supersession is anchored on the moment a run **parked**, not the moment it started. So a turn
that starts while run A is still executing, before A reaches its wait, does not supersede A:

| Time | Event | Result |
|---|---|---|
| t=0 | msg 1 → run A starts an API call that takes 20s | A is `running` |
| t=10s | msg 2 → run B starts | B is seeded **without** A's state, because A is still running, and replies |
| t=20s | A reaches the wait and parks | |
| t=3h | A wakes. B started *before* A parked | A resumes and replies too: **two replies** |

This follows from the anchor in the code. No test covers it directly. If an agent puts slow nodes
in front of a wait, keep the work before the wait short. Alternatively, have the post-wait branch
re-check whether a reply is still needed, for example by looking up the ticket's latest status
with an `api` node first.

## Where it cannot go

**Not inside an agent called by `agent_call`.** A sub-agent run has no caller left to answer
when it wakes, so a wait in one parks with nowhere to deliver. `validate_agent` rejects a direct
`agent_call` into a wait-containing agent; deeper in the chain it fails at run time instead.

Long waits are cheap but not free in attention: every paused run is a checkpoint someone may
have to reason about later. Prefer the shortest delay that does the job.

## Worked example: policy copy not issued yet

The customer asks for their policy copy. The policy is not issued yet, so the agent waits an hour
and looks again. `vehicle_number` is written by an earlier `llm_agent` extraction node, and
`send_copy` / `escalate` are ordinary reply nodes. All three are left out here.

```json
{"nodes": [
  {"name": "lookup_policy", "type": "communication", "subtype": "api",
   "config": {"node_type": "communication", "communication_type": "api",
              "api": {"host_config_key": "MIS_HOST", "path": "/api/policy/search", "method": "POST",
                      "headers": {"Content-Type": "application/json"},
                      "body_template": "{\"vehicle_number\": {{state.vehicle_number | tojson}}}",
                      "output_key": "mis_result", "process_non_2xx": false}}},
  {"name": "cool_off", "type": "functional", "subtype": "wait",
   "config": {"node_type": "functional", "function_type": "wait",
              "wait": {"duration_seconds": 3600}}},
  {"name": "lookup_policy_again", "type": "communication", "subtype": "api",
   "config": {"node_type": "communication", "communication_type": "api",
              "api": {"host_config_key": "MIS_HOST", "path": "/api/policy/search", "method": "POST",
                      "headers": {"Content-Type": "application/json"},
                      "body_template": "{\"vehicle_number\": {{state.vehicle_number | tojson}}}",
                      "output_key": "mis_result", "process_non_2xx": false}}}],
 "edges": [
  {"source_node_name": "lookup_policy", "target_node_name": "send_copy",
   "edge_type": "conditional", "label": "issued",
   "condition_config": {"condition_type": "python_expression",
     "python_expression": {"expression": "state.get('mis_result', {}).get('status') == 'ISSUED'"}}},
  {"source_node_name": "lookup_policy", "target_node_name": "cool_off",
   "edge_type": "conditional", "label": "not issued",
   "condition_config": {"condition_type": "python_expression",
     "python_expression": {"expression": "state.get('mis_result', {}).get('status') != 'ISSUED'"}}},
  {"source_node_name": "cool_off", "target_node_name": "lookup_policy_again",
   "edge_type": "direct", "condition_config": {}, "label": null}]}
```

Turn 1, `"Need the policy copy for MH12AB1234"`: `lookup_policy` writes
`mis_result: {"status": "PENDING"}`, then `cool_off` parks the run. `get_run` shows
`interrupted` with `resume_at` one hour out.

Forty minutes later the customer writes `"any update?"`. That turn starts with
`vehicle_number: "MH12AB1234"` and `mis_result: {"status": "PENDING"}` already in state, seeded
from the parked run, and sees both messages in `conversation_history`. It runs `lookup_policy`
again. If the policy is still pending it parks on its own fresh one-hour wait. When the first
run's hour is up, that run is superseded by this newer turn, and only the newer turn will reply.

While testing, set `duration_seconds` to `60`, then put the real value back before going live.
