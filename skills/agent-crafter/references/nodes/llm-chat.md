# `llm` / `llm_chat`

A single LLM call. Use it for generation and rewriting — anything where you want prose back. When
you need a *structured* decision that an edge will route on, use `llm_agent` instead; its
structured output is far more reliable than parsing prose.

`llm` configs are **flat** — no sub-dicts.

```json
{"node_type": "llm", "llm_type": "llm_chat",
 "llm_id": "gpt-4o",
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

`llm_id` must be a real model from `node_catalog().llms` — do not invent one. Declare `output_key`
in `state_schema`.

## Prompts

Both prompts are Jinja2 over state: `{{message}}`, `{{state.classification.category}}`. Put the
role and rules in `system_prompt` and the per-turn data in `user_prompt_template` — that split
keeps the cached prefix stable and makes the node easier to edit later.

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
and pauses the run as `interrupted` when it falls below `confidence_threshold`. The model has to
actually emit that field, so instruct it to. `interrupt_metadata` then carries the node name,
the score, the threshold and the raw response.
