# `llm` / `llm_data_collection`

Gathers a declared set of fields and documents out of the conversation and reports what is still
missing. Use it for the "keep asking until I have everything" shape — new bank account details,
claim documents, KYC — where the agent loops back to the customer until a checklist is satisfied.

Before this node existed that took an `llm_chat` node with a hand-written prompt plus a
`python_inline` node to tally what was outstanding, rebuilt per agent. Reach for it whenever a
graph would otherwise ask "do I have everything yet?".

`llm` configs are **flat** — no sub-dicts.

```json
{"node_type": "llm", "llm_type": "llm_data_collection",
 "llm_id": "gpt-4o",
 "max_tokens": 2000,
 "system_prompt": "",
 "user_prompt_template": "{{message}}",
 "groups_type": "partner_management_queries",
 "groups": [
   {"id": "new_bank_account", "kind": "field", "min_required": 1,
    "items": [
      {"key": "new_account_bank_name", "type": "text", "compulsory": true,
       "min_confidence": 0.85, "description": "Name of the bank where the new account is opened"},
      {"key": "new_account_ifsc", "type": "text", "pattern": "^[A-Z]{4}0[A-Z0-9]{6}$",
       "compulsory": false, "min_confidence": 0.85, "description": "IFSC code of the new account"},
      {"key": "account_type", "type": "enum", "values": ["Saving", "Current"],
       "compulsory": false, "min_confidence": 0.85, "description": "Savings or current"}],
    "rules": ["The bank name and IFSC code must belong to the same bank."]},
   {"id": "accident_proof", "kind": "file", "min_required": 1,
    "items": [
      {"key": "fir_copy", "type": "file", "compulsory": false,
       "min_confidence": 0.85, "description": "Copy of the FIR filed for this accident"}],
    "rules": ["Engine or chassis number on the FIR must match the RC copy."]}]}
```

There is **no `output_key`** — the result is written to `state[groups_type]`. Declare that key in
`state_schema` as a `dict`. `groups_type` is slugified, so `"Partner Management Queries"` and
`"partner_management_queries"` land in the same place; write the slug and the two can never drift.

There is also no `parse_json_response` or `confidence_*`. The response schema is always enforced
(below), and confidence is reported per key rather than once for the whole node.

## Groups

A group is one checklist section. `kind` decides where its items come from:

- **`field`** — values the customer states in conversation. Items land in `values`.
- **`file`** — documents the customer uploads. The model reads `state["file_details"]` (populated
  by an upstream `document_classification` node, or by the run's `files`) and decides which
  classified file satisfies which key. Items land in `files`, holding a file id.

`min_required` is how many of that group's items must be present for it to count as satisfied.
`rules` are plain sentences the model checks across the group — cross-field consistency that no
single item can express.

Item fields:

| Key | Meaning |
|---|---|
| `key` | the name in `values` / `files` / `confidence`. **Unique across every group** — they are flat maps. |
| `type` | `text`, `enum` (with `values`), `number`, `date`, `file` |
| `pattern` | regex, guidance only — it is in the prompt, not enforced by the schema |
| `compulsory` | a missing compulsory item makes the group unsatisfied even if `min_required` is met |
| `min_confidence` | below it, the model nulls the value but keeps the confidence it had |
| `description` | what the model looks for. This does the real work — be specific. |

## The output

```json
{"groups_type": "partner_management_queries",
 "verdict": "INCOMPLETE",
 "values": {"new_account_bank_name": "State Bank of India",
            "new_account_ifsc": "SBIN0000023", "account_type": null},
 "files": {"fir_copy": null},
 "confidence": {"new_account_bank_name": 0.92, "new_account_ifsc": 0.88,
                "account_type": 0.0, "fir_copy": 0.0},
 "results": {"new_bank_account": {"keys": ["new_account_bank_name", "new_account_ifsc",
                                           "account_type"],
                                  "min_required": 1, "found": 2, "satisfied": true,
                                  "rule_failures": []},
             "accident_proof": {"keys": ["fir_copy"], "min_required": 1, "found": 0,
                                "satisfied": false,
                                "rule_failures": [{"rule": "...", "confidence": 0.74,
                                                   "reason": "...", "evidence": ["..."]}]}},
 "missing_fields": ["account_type"],
 "missing_files": ["fir_copy"]}
```

`satisfied` needs `found >= min_required` **and** every compulsory key present **and** no rule
failures. `verdict` is `COMPLETE` only when every group is satisfied.

## The shape is guaranteed

The runner generates a strict JSON Schema from your `groups` and enforces it with
`with_structured_output`. `verdict` is always present and always one of the two strings; the
`values` / `files` / `confidence` keys are exactly the ones you configured; `results` holds
exactly your group ids; each `min_required` is pinned so it cannot be mis-echoed.

So an edge can route on it without a guard — but **not with `state_key_equals`**. That handler
does a flat `state.get(key)`; it has no dotted-path support, so a key like
`"partner_management_queries.verdict"` reads as empty and the run fails with "matched no branch".

Use `python_expression`, one boolean per edge, evaluated in order:

```json
{"condition_type": "python_expression"}
```

| edge → | `expression` |
|---|---|
| the "carry on" node | `state.get('partner_management_queries', {}).get('verdict') == 'COMPLETE'` |
| the "ask again" node | `True` |

They are evaluated in order, first truthy wins, so the second is the else-branch. Every edge needs
a non-empty expression and the run fails if none matches — always leave one that holds.

If you would rather use `state_key_equals`, put a one-line `python_inline` node after the
collector that lifts the verdict to a top-level key
(`return {"collection_verdict": state.get("partner_management_queries", {}).get("verdict")}`) and
route on that. Either way the value is guaranteed present — it can never be `null`.

What the schema does *not* pin is arithmetic — `found` is an integer, and nothing stops the model
miscounting. Route on `verdict` and `missing_fields`, which the model reasons about directly;
treat `found` as a summary, not a number to compute against.

## The loop

The node is built to run repeatedly, and merging is why:

```
collect ──▶ verdict == "INCOMPLETE" ──▶ ask for what is missing ──▶ (next turn) collect
        └─▶ verdict == "COMPLETE"   ──▶ carry on
```

On each run the previous `state[groups_type]` is fed back to the model as already-collected and
it carries forward every non-null value. A field captured on turn one survives turn three. That
means the agent must be **multi-turn** — declare an `is_session_id` key in `state_schema`, or
each turn starts blank and the loop never terminates.

The node after the `INCOMPLETE` branch usually reads `missing_fields` / `missing_files` to write
the follow-up question. An `llm_chat` node with those interpolated into its
`user_prompt_template` is enough.

## Config errors fail the run

An unnamed group, an unnamed item, a group with no items, or a key used twice returns `_error`
and stops the run. Nothing is silently skipped — a dropped group would still produce a successful
run and a confident verdict computed over less than you configured, which is worse than a
failure. If a run dies with `Data collection config is invalid — …`, the message names every
problem at once.
