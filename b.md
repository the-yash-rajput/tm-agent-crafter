
---

# Second fix: conditional edge branch values

`edges.md` led with a section headed *"`label` is the branch value, not a caption — this is the part people get wrong."* That's true for `llm_router` and nothing else. Per `services/runtime/graph_runtime/builder.py` and `edge_router.py`:

| `condition_type` | Branch value read from | `label` used? |
|---|---|---|
| `state_key_equals` | `condition_config.state_key_equals.value` | no |
| `python_expression` | `condition_config.python_expression.expression` | no |
| `llm_router` | the edge's `label` | yes |

Neither type the doc recommends routes on `label`.

The concrete breakage: the `state_key_equals` example omitted `value` entirely, so `condition_value` fell back to `""` on every edge and nothing could match —

```
EdgeRoutingError: state_key_equals: key='intent' value='refund'
matched no branch (configured values: ['', ''])
```

Every `state_key_equals` graph authored from that example failed at the routing step. It survived unnoticed because the doc's house pattern is paired `python_expression` negations, which never touch `label`.

Also documented, from the same read of the runtime:

- `state_key_equals` compares `str(...).strip().lower()` on both sides; a duplicate `value` across edges is a hard failure, not first-wins.
- The router's `condition_type` is taken from the **first** conditional edge out of a node — mixing types in one group silently reinterprets the rest.
- Edges are fetched with no `order_by` and `Edge` declares no `Meta.ordering`, so `python_expression` evaluation order is DB-dependent. Expressions must be mutually exclusive rather than relying on authored order.
- `validate_agent` catches none of these; they surface only on a real run.

Same correction carried into `llm-agent.md` ("the enum values become your edge `label`s") and `debugging.md`, whose symptom table now lists both routing errors.

Version bumped again to **0.1.2**.
