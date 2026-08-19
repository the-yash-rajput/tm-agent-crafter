# Edges

```json
{"source_node_name": "check", "target_node_name": "odd",
 "edge_type": "conditional", "label": "odd",
 "condition_config": {"condition_type": "python_expression",
                      "python_expression": {"expression": "not state.get('is_even', False)"}}}
```

`edge_type` is `direct` or `conditional`. A `direct` edge takes `"condition_config": {}` and a
null/empty `label`.

## The two condition shapes

`condition_config` is a tagged union: `condition_type` names the variant, and a sibling key of
the *same name* holds its settings.

```json
{"condition_type": "state_key_equals",  "state_key_equals":  {"key": "intent", "value": "refund"}}
{"condition_type": "python_expression", "python_expression": {"expression": "state.get('score', 0) > 0.8"}}
```

- **`state_key_equals`** — reads `state[key]` and follows the edge whose **`value`** equals it.
  Best when an LLM emits a fixed `enum` of categories: the `value`s and the enum are the same
  list, so coverage is easy to eyeball.
- **`python_expression`** — evaluates each edge's expression against `state` and follows the
  first one that returns truthy. Use `state.get('k', default)` rather than `state['k']`; a
  missing key raises and fails the run instead of routing.

Use these two only. `node_catalog` also lists a third type, `llm_router` — it is **not used
here, so do not author it**, whatever the catalog reports. It is hidden from the frontend, and
it is the one type that routes on `label`, so it behaves unlike everything else in this
document. If you meet one in an existing agent that is what it is doing; leave it alone, or
convert it to `state_key_equals` on the same key with a `value` per branch.

## Where the branch value lives — read this before authoring a conditional

Each condition type reads a *different* field, and neither reads `label`. Putting the branch
value in the wrong one is the most common way a graph that validates cleanly still fails at
runtime.

| `condition_type` | Branch value read from |
|---|---|
| `state_key_equals` | `condition_config.state_key_equals.value`, **per edge** |
| `python_expression` | `condition_config.python_expression.expression`, **per edge** |

**`label` is a caption.** The canvas shows it; nothing routes on it. Give it the same text as
the branch value so the graph reads clearly, but changing it can never change where a run goes.

### `state_key_equals` needs a `value` on every edge

`key` names the state key to read; `value` is what *this* edge matches. `key` is repeated
identically on every edge out of the node, `value` differs per edge:

```json
{"source_node_name": "classify", "target_node_name": "handle_refund",
 "edge_type": "conditional", "label": "refund",
 "condition_config": {"condition_type": "state_key_equals",
                      "state_key_equals": {"key": "intent", "value": "refund"}}}

{"source_node_name": "classify", "target_node_name": "handle_claim",
 "edge_type": "conditional", "label": "claim",
 "condition_config": {"condition_type": "state_key_equals",
                      "state_key_equals": {"key": "intent", "value": "claim"}}}
```

Omit `value` and it defaults to `""`, so no edge can ever match and every run dies at the
routing step:

```
EdgeRoutingError: state_key_equals: key='intent' value='refund'
matched no branch (configured values: ['', ''])
```

Both sides are compared as `str(...).strip().lower()`, so matching is case- and
whitespace-insensitive — `"Refund"` matches `"refund"`. Two edges from the same source with the
same `value` is a hard failure, not first-wins:

```
EdgeRoutingError: state_key_equals: key=... value=... matched multiple branches [...]
— duplicate condition_value in graph config
```

## One condition type per source node

All conditional edges leaving a node are routed by a single router, and its type is taken from
the **first** edge in the group. Mixing types across edges from one source does not error — the
others are silently reinterpreted under the first edge's type, which usually means their branch
value is read from a field they never set. Keep every conditional edge out of a node on the same
`condition_type`.

If `condition_type` is absent from `condition_config`, it defaults to `state_key_equals`.

## Cover every branch — there is no default

If the source node produces a value no edge matches, the run fails to route. It does not fall
through to a default, and there is no implicit else.

### Do not rely on edge order

Edges are read back without an explicit sort, so evaluation order for `python_expression` is
database-dependent rather than the order you authored them in. Never write expressions that
depend on an earlier one having been tried first — make them mutually exclusive so that exactly
one is truthy for any state.

### The house pattern: paired complementary expressions

Production agents here overwhelmingly use two `python_expression` edges that are exact
negations. Coverage is total by construction and, because exactly one is ever truthy, order
cannot matter:

```json
{"source_node_name": "topic_gate", "target_node_name": "payout_flow",
 "edge_type": "conditional", "label": "Payout Related",
 "condition_config": {"condition_type": "python_expression",
   "python_expression": {"expression": "state.get('topic_gate', {}).get('is_payout_related', False)"}}}

{"source_node_name": "topic_gate", "target_node_name": "reject",
 "edge_type": "conditional", "label": "Not Payout Related",
 "condition_config": {"condition_type": "python_expression",
   "python_expression": {"expression": "not state.get('topic_gate', {}).get('is_payout_related', False)"}}}
```

Reach for this on any boolean split, and reserve `state_key_equals` for genuine multi-way
fan-out.

For a multi-way split, give every enum value its own edge **including the fallback**
(`unclear`, `other`). An LLM will eventually emit it.

## Checking your work

`validate_agent` reports `node_count`/`edge_count` and catches dangling references and
unreachable nodes. It does **not** check that a `state_key_equals` edge has a `value`, that
branch values are unique, or that the branches cover what the source node can emit — those
surface only as an `EdgeRoutingError` on a real run. Read `state_snapshots` afterwards to see
what the source node actually wrote (see `debugging.md`).
