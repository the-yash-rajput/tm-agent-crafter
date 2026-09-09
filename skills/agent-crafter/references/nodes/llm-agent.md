# `llm` / `llm_agent`

ReAct-style tool-using LLM node, and — more importantly in practice — **the reliable way to get
structured JSON out of a model.** Every classifier in the production agents here is an
`llm_agent` with structured output enabled.

`llm` configs are **flat**.

```json
{"node_type": "llm", "llm_type": "llm_agent",
 "llm_id": "gpt-4o",
 "system_prompt": "You are an intent classifier for a payout support channel.",
 "user_prompt_template": "Ticket: {{state.ticketId}}\n\nUser message:\n{{message}}",
 "max_tokens": 300,
 "output_key": "classification",
 "structured_output_enabled": true,
 "structured_output_schema": "{\"type\":\"object\",\"required\":[\"category\",\"confidence\",\"reason\"],\"properties\":{\"category\":{\"type\":\"string\",\"enum\":[\"refund\",\"statement\",\"unclear\"]},\"confidence\":{\"type\":\"number\",\"minimum\":0,\"maximum\":1},\"reason\":{\"type\":\"string\"}},\"additionalProperties\":false}",
 "parse_json_response": false,
 "confidence_threshold_enabled": false,
 "confidence_threshold": 0.7,
 "confidence_key": "confidence"}
```

## `structured_output_schema` is a **string**

It holds a JSON Schema serialised as JSON, not a nested object. This trips people up constantly —
if you pass an object the node will not behave as intended.

Design the schema for the edges that follow it:

- Put an **`enum`** on the routing field. The enum values become your edge branch values, so
  coverage is checkable by eye. For `state_key_equals` edges that means one edge per enum value,
  each with `state_key_equals.value` set to it — see `edges.md`, which field carries the branch
  value depends on the condition type.
- Always include a fallback value (`unclear`, `other`) and give it a real branch. A model will
  emit it eventually, and a value no edge covers fails routing.
- Add `"additionalProperties": false` so the model cannot invent fields.
- A `confidence` number lets a downstream edge demand a floor:
  `state.get('classification', {}).get('confidence', 0) >= 0.7`.
- A one-sentence `reason` costs almost nothing and turns `state_snapshots` into a readable audit
  trail when you are debugging a misroute.

## Two-stage classification

The house pattern for messy inbound text is a cheap **gate** followed by a precise
**classifier** — e.g. a `gpt-4o-mini` node deciding only "is this in scope?", then a `gpt-4o`
node picking the exact bucket. It is cheaper and measurably more accurate than one big prompt,
because each model does one job.

The same `output_key`, prompt, Langfuse and confidence-gate notes as `llm_chat` apply — see
`llm-chat.md`.
