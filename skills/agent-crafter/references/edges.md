# Edges

```json
{"source_node_name": "check", "target_node_name": "odd",
 "edge_type": "conditional", "label": "odd",
 "condition_config": {"condition_type": "python_expression",
                      "python_expression": {"expression": "not state.get('is_even', False)"}}}
```

`edge_type` is `direct` or `conditional`. A `direct` edge takes `"condition_config": {}` and a
null/empty `label`.

## The three condition shapes

`condition_config` is a tagged union: `condition_type` names the variant, and a sibling key of
the *same name* holds its settings.

```json
{"condition_type": "state_key_equals",  "state_key_equals":  {"key": "intent"}}
{"condition_type": "python_expression", "python_expression": {"expression": "state.get('score', 0) > 0.8"}}
{"condition_type": "llm_router",        "llm_router":        {"routing_key": "next_step"}}
```

- **`state_key_equals`** — reads `state[key]` and follows the edge whose `label` equals that
  value. Best when an LLM emits a fixed `enum` of categories: the labels and the enum are the
  same list, so coverage is easy to eyeball.
  > **Top-level keys only.** The lookup is a flat `state.get(key)` — there is no dotted-path
  > support, so `"result.verdict"` reads as empty and the run fails with "matched no branch".
  > To route on something nested, use `python_expression`, or lift the value to a top-level key
  > with a one-line `python_inline` node first.
- **`python_expression`** — a **boolean per edge**, not one value matched against labels. Every
  edge in the branch carries its own expression; they are evaluated in source order and the first
  truthy one wins, like `if` / `elif`. The `label` is a caption here, so make the last edge's
  expression one that always holds — if none matches, the run fails. Use
  `state.get('k', default)` rather than `state['k']`; a missing key raises instead of routing.
- **`llm_router`** — routes on a key the LLM wrote. Hidden from the frontend by default, so
  prefer one of the other two unless the user asks for it.

## `label` is the branch value, not a caption

This is the part people get wrong. On a conditional edge the `label` is the value being matched.
One edge per possible value. If the source node can produce a value no edge labels, the run
fails to route — it does not fall through to a default.

## The house pattern: paired complementary expressions

Production agents here overwhelmingly use two `python_expression` edges that are exact negations:

```json
{"label": "Payout Related",     "expression": "state.get('topic_gate', {}).get('is_payout_related', False)"}
{"label": "Not Payout Related", "expression": "not state.get('topic_gate', {}).get('is_payout_related', False)"}
```

Coverage is then total by construction — there is no third case to forget. Reach for this on
any boolean split, and reserve `state_key_equals` for genuine multi-way fan-out.

For a multi-way split, enumerate every enum value **including the fallback** (`unclear`,
`other`), and give the fallback its own branch. An LLM will eventually emit it.

## Checking your work

`validate_agent` reports `node_count`/`edge_count` and catches dangling references and
unreachable nodes. It cannot tell you a branch value is unreachable in practice — for that, read
`state_snapshots` after a real run (see `debugging.md`).
