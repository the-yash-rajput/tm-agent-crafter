# `llm` / `llm_agent`

**The reliable way to get structured JSON out of a model.** Every classifier in the production
agents here is an `llm_agent` with structured output enabled. Despite the name it has **no
tools**: the runtime agent is built with `tools=[]`, so it answers in one step like `llm_chat`,
but with the response schema enforced.

`llm` configs are **flat**.

```json
{"node_type": "llm", "llm_type": "llm_agent",
 "llm_id": 3,
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

## AzureOpenAI only, and it fails quietly

Only an `AzureOpenAI` LLM row runs this node as an agent. With any other provider (`AWSBedRock`)
it **silently falls back to `llm_chat`**: the run succeeds, but `structured_output_schema` is not
enforced. If anything downstream depends on the schema holding, pick an Azure `llm_id`. For a
fixed checklist on Bedrock, `llm_data_collection` is the alternative.

`llm_id`, `temperature`, `reasoning_effort` and `max_tokens` work exactly as in `llm-chat.md`.

## `structured_output_schema`

The runtime accepts a JSON object or a JSON-encoded string. The canvas saves it back as a
**string**, so write the string form and payloads stay diff-stable across UI edits. Enabling
structured output with an empty schema fails the run, and so does a string that is not valid JSON.
A schema without a `title` gets one from the node name.

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

## Worked example: pull the policy identifier out of a message

Customer: `"Hi, I need the policy copy for vehicle MH12AB1234"`.

```json
{"name": "data_identifier", "type": "llm", "subtype": "llm_agent",
 "config": {"node_type": "llm", "llm_type": "llm_agent", "llm_id": 3, "max_tokens": 300,
            "system_prompt": "Extract the identifiers a motor-insurance customer gives. Vehicle numbers look like MH12AB1234. Leave a field as an empty string when it is not in the message.",
            "user_prompt_template": "{{message}}",
            "output_key": "identifier_extraction",
            "structured_output_enabled": true,
            "structured_output_schema": "{\"type\":\"object\",\"properties\":{\"has_identifier\":{\"type\":\"boolean\"},\"vehicle_number\":{\"type\":\"string\"},\"policy_number\":{\"type\":\"string\"},\"confidence\":{\"type\":\"number\"}},\"required\":[\"has_identifier\",\"vehicle_number\",\"policy_number\",\"confidence\"],\"additionalProperties\":false}",
            "parse_json_response": false,
            "confidence_threshold_enabled": false, "confidence_threshold": 0.7, "confidence_key": "confidence"}}
```

State after:
`identifier_extraction: {"has_identifier": true, "vehicle_number": "MH12AB1234", "policy_number": "", "confidence": 0.94}`.

| Edge to | `expression` |
|---|---|
| `lookup_policy` (an `api` node) | `state.get('identifier_extraction', {}).get('has_identifier', False)` |
| `ask_for_identifier` (an `llm_chat` reply) | `not state.get('identifier_extraction', {}).get('has_identifier', False)` |

The `api` body then uses `{{state.identifier_extraction.vehicle_number | tojson}}`.
