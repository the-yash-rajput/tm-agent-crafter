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
 "llm_id": 3,
 "max_tokens": 2000,
 "system_prompt": "",
 "user_prompt_template": "{{message}}",
 "output_key": "",
 "groups": [
   {"id": "new_bank_account", "min_required": 1,
    "items": [
      {"key": "new_account_bank_name", "type": "text", "compulsory": true,
       "min_confidence": 0.85, "description": "Name of the bank where the new account is opened"},
      {"key": "new_account_ifsc", "type": "text", "pattern": "^[A-Z]{4}0[A-Z0-9]{6}$",
       "compulsory": false, "min_confidence": 0.85, "description": "IFSC code of the new account"},
      {"key": "account_type", "type": "enum", "values": ["Saving", "Current"],
       "compulsory": false, "min_confidence": 0.85, "description": "Savings or current"},
      {"key": "cancel_check", "type": "file", "compulsory": false,
       "min_confidence": 0.85, "description": "A cancelled cheque for the new account"}],
    "rules": ["The bank name and IFSC code must belong to the same bank."]},
   {"id": "accident_proof", "min_required": 1,
    "items": [
      {"key": "fir_copy", "type": "file", "compulsory": false,
       "min_confidence": 0.85, "description": "Copy of the FIR filed for this accident"}],
    "rules": ["Engine or chassis number on the FIR must match the RC copy."]}]}
```

The result is written to `state[output_key]`, and **a blank `output_key` means the node's name**.
The examples below assume the node is named `collect_bank_details`, so its result lands at
`state["collect_bank_details"]`; it needs no `state_schema` entry. Keys are
slugified, so a node named "Collect Bank Details" also writes `collect_bank_details`.

The blank default is resolved on every run, so it follows the node through renames — which means
renaming the node changes the state key, and every `state.collect_bank_details` reference
downstream (prompts, edge expressions) stops matching. If anything reads the result, set
`output_key` explicitly to pin it.

An explicit `output_key` is used **exactly as typed** and must already be a slug: lowercase
letters, digits and underscores. `bankCollection` or `Bank Collection` fails the run with the
suggested slug in the error, and is never rewritten for you. If it were rewritten, an edge written
against the typed key would silently never match. The per-turn keys `message`,
`conversation_history`, `file_details` and `session_id` are refused too, because they are
overwritten or stripped every turn.

`llm_id` is the integer id of an LLM row (see `llm-chat.md`). `max_tokens` defaults to 2000,
because the verdict object is larger than a chat reply. Raise it for many groups.

There is also no `parse_json_response` or `confidence_*`. The response schema is always enforced
(below), and confidence is reported per key rather than once for the whole node.

## Groups

A group is one checklist section. **Type is per item**, so a group can mix things the customer
tells you with documents they upload — `new_bank_account` above wants a bank name, an IFSC and a
cancelled cheque:

- **`text` / `enum` / `number` / `date`** — values the customer states in conversation.
- **`file`** — a document the customer uploads. The model reads `state["file_details"]` (populated
  by an upstream `document_classification` node, or by the run's `files`) and decides which
  classified file satisfies the key. The item's value is that **file id**, or `null`.

Every item's result lands in the group's single `values` object, whatever its type.

`min_required` is how many of that group's items must be present for it to count as satisfied.
`rules` are plain sentences the model checks across the group — cross-field consistency that no
single item can express.

**Write every required key.** This node has no defaults for them — a missing or wrong value is a
config error that stops the run, not something quietly filled in.

Group keys, all required:

| Key | Rule |
|---|---|
| `id` | non-empty; slugified |
| `min_required` | whole number from 1 to the group's item count |
| `items` | non-empty list |
| `rules` | list of non-empty strings — **`[]` when there are none**, not omitted |

Item keys:

| Key | Required | Rule |
|---|---|---|
| `key` | yes | the name in the group's `values` / `confidence` / `types`. **Unique across every group**, so a key means one thing wherever a downstream prompt reads it. |
| `type` | yes | `text`, `enum`, `number`, `date` or `file` — mix freely within a group |
| `values` | for `enum` | non-empty list of strings — the allowed answers |
| `min_confidence` | yes | number from 0 to 1. Below it, the model nulls the value but keeps the confidence it had. |
| `pattern` | no | regex, guidance only — it is in the prompt, not enforced by the schema |
| `compulsory` | no | default `false`. A missing compulsory item makes the group unsatisfied even if `min_required` is met. |
| `description` | no | what the model looks for. Optional, but it does the real work — be specific. |

## The output

The object in state is only `verdict` and `results`. Everything about a group lives inside its
entry in `results`:

```json
{"verdict": "INCOMPLETE",
 "results": {
   "new_bank_account": {
     "min_required": 1, "found": 3, "satisfied": true,
     "values": {"new_account_bank_name": "State Bank of India", "new_account_ifsc": "SBIN0000023",
                "account_type": null, "cancel_check": "4ed30d56-56ad-415b-b956-afe70cc29ac6"},
     "confidence": {"new_account_bank_name": 0.92, "new_account_ifsc": 0.88,
                    "account_type": 0.0, "cancel_check": 1.0},
     "types": {"new_account_bank_name": "text", "new_account_ifsc": "text",
               "account_type": "enum", "cancel_check": "file"},
     "missing": ["account_type"],
     "rule_failures": []},
   "accident_proof": {
     "min_required": 1, "found": 0, "satisfied": false,
     "values": {"fir_copy": null},
     "confidence": {"fir_copy": 0.0},
     "types": {"fir_copy": "file"},
     "missing": ["fir_copy"],
     "rule_failures": [{"rule": "Engine number or chassis number on the FIR must match the RC copy.",
                        "confidence": 0.74,
                        "reason": "Chassis number on the FIR differs from the RC copy in one character.",
                        "evidence": ["FIR: MA3EYD32S00123456", "RC: MA3EYD32S00123458"]}]}}}
```

`types` says which values are file ids. It is copied from your config by the runner after the
model answers, so it is always exactly what you configured.

`satisfied` needs `found >= min_required` **and** every compulsory key present **and** no rule
failures. `verdict` is `COMPLETE` only when every group is satisfied.

## The shape is guaranteed

The runner generates a strict JSON Schema from your `groups` and enforces it with
`with_structured_output`. `verdict` is always present and always one of the two strings;
`results` holds exactly your group ids; inside each group, `min_required` is pinned so it cannot
be mis-echoed, `values`/`confidence` hold exactly that group's keys, and `missing` can only name
that group's keys. A `file` item's slot only accepts a string, so a model answering `true`
instead of a file id is rejected.

That guarantee is **AzureOpenAI's** strict mode. An `AWSBedRock` row uses non-strict tool
calling, so the runner checks the answer itself and fails the run with
`Data collection model omitted group(s): …` when a configured group is missing.

So an edge can route on it without a guard — but **not with `state_key_equals`**. That handler
does a flat `state.get(key)`; it has no dotted-path support, so a key like
`"collect_bank_details.verdict"` reads as empty and the run fails with "matched no branch".

Use `python_expression`, one boolean per edge, as a pair of exact negations:

```json
{"condition_type": "python_expression"}
```

| edge → | `expression` |
|---|---|
| the "carry on" node | `state.get('collect_bank_details', {}).get('verdict') == 'COMPLETE'` |
| the "ask again" node | `state.get('collect_bank_details', {}).get('verdict') != 'COMPLETE'` |

Edge evaluation order is not guaranteed (see `edges.md`), so do not use a bare `True` as an
else-branch — make the two expressions mutually exclusive so exactly one is truthy for any
state. The run fails if none matches.

If you would rather use `state_key_equals`, put a small `python_inline` node after the
collector that lifts the verdict to a top-level key, and route on that:

```python
def run(state):
    state["collection_verdict"] = state.get("collect_bank_details", {}).get("verdict")
    return state
```

Return the whole `state`. Returning only `{"collection_verdict": …}` replaces the state and drops
everything else (see `python-inline.md`). Either way the verdict is guaranteed present and can
never be `null`.

What the schema does *not* pin is arithmetic — `found` is an integer, and nothing stops the model
miscounting. Route on `verdict` and each group's `missing`, which the model reasons about directly;
treat `found` as a summary, not a number to compute against.

## The loop

The node is built to run repeatedly, and merging is why:

```
collect ──▶ verdict == "INCOMPLETE" ──▶ ask for what is missing ──▶ (next turn) collect
        └─▶ verdict == "COMPLETE"   ──▶ carry on
```

On each run the previous `state[<key>]` is fed back to the model as already-collected and
it carries forward every non-null value. A field captured on turn one survives turn three. That
means every turn must run in **the same session**: pass the same `session_id` (or `external_id`)
to `run_agent`, or each turn starts blank and the loop never terminates. Also declare an
`is_session_id` key (the ticket id) in `state_schema`. Its value keys the uploaded documents, so
files sent on turn one, including ones turtle-doc processed for the same ticket, are still in
`file_details` on turn three. How a turn is seeded from the previous one, including during a
`wait`, is in `wait.md`.

The node after the `INCOMPLETE` branch writes the follow-up question from each group's `missing`.
There is no single flat list, so walk `results` — prompts are Jinja over `state`, so an `llm_chat`
node's `user_prompt_template` can do it directly:

```jinja
Still needed:
{% for id, group in state.collect_bank_details.results.items() %}{% for key in group.missing %}
- {{ key }}{% if group.types[key] == 'file' %} (please upload){% endif %}
{% endfor %}{% endfor %}
```

`types` lets the question say "please upload" for documents and ask for everything else in words.

> **Write `group['values']`, never `group.values`.** Jinja tries attribute access first, and
> `values` is a dict method — so `{{ group.values }}` renders `<built-in method values…>` instead
> of the data, with no error. `missing`, `types`, `confidence` and `rule_failures` are safe with
> dot access; `values` is the one that collides.

## Config errors fail the run

Anything outside the tables above returns `_error` and stops the run: an unnamed group or item, a
group with no items, a key used twice, an unknown item `type`, an
`enum` with no values, `min_required` or `min_confidence` out of range, an empty rule, a missing
`rules` list, or more than **1000 `enum` values across the whole node**, which strict mode cannot
accept (`too many choices`). Nothing is skipped and nothing is defaulted — a dropped group or a substituted value
would still produce a successful run and a confident verdict over something other than what you
configured, which is worse than a failure. If a run dies with
`Data collection config is invalid — …`, the message names every problem at once.

## Worked example: bank details for a claim payout, over two turns

Node `payout_details` (explicit `output_key`, so renaming the node cannot break the edges), placed
after a `document_classification` node that has a `CANCELLED_CHEQUE` category:

```json
{"name": "payout_details", "type": "llm", "subtype": "llm_data_collection",
 "config": {"node_type": "llm", "llm_type": "llm_data_collection", "llm_id": 3, "max_tokens": 2000,
            "system_prompt": "These are motor insurance claim payouts in India.",
            "user_prompt_template": "{{message}}", "output_key": "payout_details",
            "groups": [
              {"id": "bank_account_details", "min_required": 4,
               "items": [
                 {"key": "account_holder_name", "type": "text", "compulsory": true, "min_confidence": 0.85,
                  "description": "Name of the account holder exactly as the customer states it"},
                 {"key": "account_number", "type": "text", "compulsory": true, "min_confidence": 0.9,
                  "description": "Bank account number. Text, so leading zeros are kept"},
                 {"key": "ifsc_code", "type": "text", "pattern": "^[A-Z]{4}0[A-Z0-9]{6}$",
                  "compulsory": true, "min_confidence": 0.9, "description": "11-character IFSC of the branch"},
                 {"key": "cancelled_cheque", "type": "file", "compulsory": true, "min_confidence": 0.85,
                  "description": "A cancelled cheque for this same account"}],
               "rules": ["The IFSC code must belong to the bank printed on the cheque."]}]}}
```

**Turn 1**, `"Account is in my name Rahul Sharma, a/c 001234567890"`, no upload:

```json
{"payout_details": {"verdict": "INCOMPLETE", "results": {"bank_account_details": {
   "min_required": 4, "found": 2, "satisfied": false,
   "values": {"account_holder_name": "Rahul Sharma", "account_number": "001234567890",
              "ifsc_code": null, "cancelled_cheque": null},
   "confidence": {"account_holder_name": 0.95, "account_number": 0.97, "ifsc_code": 0.0, "cancelled_cheque": 0.0},
   "types": {"account_holder_name": "text", "account_number": "text", "ifsc_code": "text", "cancelled_cheque": "file"},
   "missing": ["ifsc_code", "cancelled_cheque"], "rule_failures": []}}}}
```

The `!= 'COMPLETE'` edge goes to an `llm_chat` reply built with the "Still needed" loop above:
*"Thanks! I still need your IFSC code, and please upload a cancelled cheque."*

**Turn 2**, `"IFSC HDFC0001234"` plus a cheque photo. Classification files the photo under
`CANCELLED_CHEQUE`, and the collector carries turn 1's values forward. The result is
`verdict: "COMPLETE"`, with `ifsc_code: "HDFC0001234"` and `cancelled_cheque` holding the photo's
file id. The `== 'COMPLETE'` edge moves on, for example to a `document_extraction` of the cheque
and a `python_inline` that checks the typed account number against it.

