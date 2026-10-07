# `llm` / `llm_chat`

A single LLM call. Use it for generation and rewriting — anything where you want prose back. When
you need a *structured* decision that an edge will route on, use `llm_agent` instead; its
structured output is far more reliable than parsing prose.

`llm` configs are **flat** — no sub-dicts.

```json
{"node_type": "llm", "llm_type": "llm_chat",
 "llm_id": 3,
 "system_prompt": "You are a friendly support assistant.",
 "user_prompt_template": "User said: {{message}}\n\nWrite a short reply.",
 "max_tokens": 300,
 "output_key": "response",
 "parse_json_response": false,
 "use_langfuse_prompt": false,
 "langfuse_prompt_name": "",
 "confidence_threshold_enabled": false,
 "confidence_threshold": 0.7,
 "confidence_key": "confidence"}
```

`output_key` does not need a `state_schema` entry. The catalog default is `llm_response`. Always
set it: omitting the key also gives `llm_response`, but an empty string `""` is used as-is, and the
answer lands under the key `""`.

## Choosing the model: `llm_id`

`llm_id` is the **integer id** of an `ai_agent.LLM` row, not a model name. `"gpt-4o"` saves
fine, passes `validate_agent`, and then fails the run with `LLM record 'gpt-4o' not found`. Take
the id from `node_catalog().llms`. If the catalog only shows `model_name` / `provider` / `model_id`
and no `id`, ask the user for the id rather than guessing. The row must be `ACTIVE`, and only
`AzureOpenAI` and `AWSBedRock` providers run.

Provider, endpoint and deployment come from that row. Two settings can be overridden per node and
fall back to the row's value when omitted or `""`:

| Key | Rule (checked at save time) |
|---|---|
| `temperature` | a number from 0.0 to 2.0 |
| `reasoning_effort` | only if the chosen LLM row has `supports_reasoning_effort`; otherwise the save is rejected |

`max_tokens` has no row-level fallback. It defaults to 1000 per node.

## Prompts

Both prompts are Jinja2 over state: `{{message}}`, `{{state.classification.category}}`. Put the
role and rules in `system_prompt` and the per-turn data in `user_prompt_template` — that split
keeps the cached prefix stable and makes the node easier to edit later. Templates see only
`message` and `state`, so any other key needs the `state.` prefix: `{{policy_number}}` renders
empty without an error. A template with a Jinja syntax error is sent **raw**, braces and all,
again without an error. Check a new prompt once in the run's Langfuse trace, which shows the
rendered text. `state_snapshots` hold state, not prompts.

Conversation history is injected automatically; you neither declare nor interpolate it. The
runner also honours `use_system_chat_history`, and `prompt_source` / `prompt_name` /
`prompt_label` for pulling a prompt from Langfuse instead of inline (`use_langfuse_prompt` plus
`langfuse_prompt_name` is the config-level form).

## `parse_json_response`

Set it when you want a dict in state rather than a string, and say so in the `system_prompt`. It
is best-effort parsing of prose, so it fails on stray markdown fences or a chatty preamble. For
anything an edge routes on, prefer `llm_agent` with `structured_output_enabled`.

## Confidence gate (human-in-the-loop)

With `confidence_threshold_enabled: true`, the runner reads `confidence_key` out of the response
and pauses the run as `interrupted` when it falls below `confidence_threshold`.
`interrupt_metadata` then carries the node name, the score, the threshold and the raw response.
The reviewer's approved or edited answer replaces the model's in `output_key`.

The gate is silent when it cannot read a score, so set it up deliberately:

- The response must be a **dict**: turn on `parse_json_response` (or use `llm_agent` with
  structured output) and tell the model to emit the key.
- A missing or non-numeric score means **no review**, and the run carries on.
- `confidence_threshold: 0` is read as "unset" and becomes 0.7. To never pause, turn the gate off.

## Worked example: write the "still pending" reply

After an `api` lookup finds the policy is not issued yet, this node writes the customer reply.

```json
{"name": "reply_pending", "type": "llm", "subtype": "llm_chat",
 "config": {"node_type": "llm", "llm_type": "llm_chat", "llm_id": 3, "max_tokens": 200,
            "temperature": 0.3,
            "system_prompt": "You are a polite motor-insurance support agent. Reply in under 60 words. Never promise a time you were not given.",
            "user_prompt_template": "Customer message: {{message}}\nPolicy status from MIS: {{state.mis_result.status}}\nVehicle: {{state.vehicle_number}}\n\nTell the customer the policy is still being issued and that we will share the copy as soon as it is ready.",
            "output_key": "reply", "parse_json_response": false,
            "use_langfuse_prompt": false, "langfuse_prompt_name": "",
            "confidence_threshold_enabled": false, "confidence_threshold": 0.7, "confidence_key": "confidence"}}
```

With `message: "need my policy copy for MH12AB1234"` and `mis_result: {"status": "PENDING"}`,
the run ends with
`reply: "Thanks for reaching out! Your policy for MH12AB1234 is still being issued. We'll share the copy with you as soon as it's ready."`.
The caller (or the ticket integration) sends `state.reply` back to the customer.
