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
checkpoint; execution continues from the node after the wait.

`scheduled: false` means the pause happened but nothing will wake it. `scheduler_error_kind`
says whose problem it is: `config` is a deployment fix (the backend's callback URL or scheduler
API key is unset), `payload` is a graph bug, `transport` is an outage worth retrying. The run's
state is intact either way; an operator resumes it by hand.

## Where it cannot go

**Not inside an agent called by `agent_call`.** A sub-agent run has no caller left to answer
when it wakes, so a wait in one parks with nowhere to deliver. `validate_agent` rejects a direct
`agent_call` into a wait-containing agent; deeper in the chain it fails at run time instead.

Long waits are cheap but not free in attention: every paused run is a checkpoint someone may
have to reason about later. Prefer the shortest delay that does the job.
