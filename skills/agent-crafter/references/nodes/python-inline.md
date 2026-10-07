# `functional` / `python_inline`

Sandboxed Python. Reach for it for anything deterministic — parsing, arithmetic, reshaping state,
building a reply string. It costs nothing and never hallucinates, so prefer it over an LLM node
whenever the logic is expressible in code.

```json
{"node_type": "functional", "function_type": "python_inline",
 "python_inline": {
   "code": "def run(state):\n    n = state.get('number', 0)\n    state['is_even'] = n % 2 == 0\n    return state",
   "timeout_seconds": 20,
   "max_memory_mb": 256}}
```

`function_type` must be `python_inline`, and remember `functional` configs also carry
`agent_call` and `rag` sub-dicts — leave them at their defaults or omit them.

## The contract: return the whole state

Define `def run(state)`, mutate `state`, and **return the whole `state`**. Keys you write reach
the next node without a `state_schema` entry.

Returning only a dict of updates does **not** merge. The graph is a `StateGraph(dict)`, so
whatever `run()` returns *replaces* the state for every later node. `return {"is_even": True}`
silently wipes `message`, earlier node outputs and everything else. It is also easy to miss:
this node's `state_after` snapshot shows the merged view, so the loss only shows up as the *next*
node's `state_before` missing keys. Always end with `return state`.

## Never write `import` inside `run()`

RestrictedPython blocks it and the node fails at runtime with `__import__ not found`. You do not
need it. These are already injected as globals, so use them directly:

| Global | Notes |
|---|---|
| `re`, `json`, `math`, `random`, `statistics` | the standard modules |
| `datetime`, `date`, `timedelta`, `time` | the `datetime` module's classes. `time` is `datetime.time`, **not** the `time` module, so `time.sleep` does not exist |
| `Counter`, `Decimal`, `uuid4` | from `collections`, `decimal`, `uuid` |
| `string` | only the constants: `string.ascii_letters`, `string.digits`, `string.punctuation`, … |

Helpers for uploaded documents and nested state. They read `state["file_details"]`, so they work
once a `document_classification` node (or the run's `files`) has populated it:

| Helper | Returns |
|---|---|
| `_has_classification("PAN_CARD")` | `True` / `False`. Never raises |
| `_files_by_classification("PAN_CARD")` | the file ids in that bucket, `[]` when empty |
| `_extraction_by_classification("PAN_CARD", 1)` | the extracted fields of the 1-based *n*th file in that bucket. **Raises** when nothing matches |
| `_extraction_by_file(file_id)` | the extracted fields of one file. **Raises** on an unknown id |
| `_classification_by_file(file_id)` | that file's classification, `None` until classified. Raises on an unknown id |
| `_fetch_all_file_record()` | `{file_id: record}` for every uploaded file, `{}` when none |
| `_fetch_all_category()` | `{classification: [file_ids]}`, `{}` when none |
| `_get_or_null("mis_result.policy.status")` | walks a dotted path through nested dicts. `None` when missing |
| `_get_or_default("mis_result.policy.status", "unknown")` | the same walk. Missing or `None` gives the default. `0`, `False` and `""` come back as-is |

Call `_has_classification` or `_files_by_classification` first when a document is optional,
because the two `_extraction_by_*` helpers raise rather than return `None`.

Every other name starting with `_` is a compile error. `os`, `sys`, `subprocess`, `socket`, the
filesystem and the network are unavailable by design. To call another system, use an `api` node.

## Limits

The node runs in an isolated child process.

| Limit | Default | Config key |
|---|---|---|
| wall-clock timeout | 20 s | `timeout_seconds` |
| memory | 256 MB | `max_memory_mb` |
| source code | 64 KiB | — |
| `state` passed in, as JSON | 1 MiB | — |
| value returned, as JSON | 1 MiB | — |

A timeout fails the run with `Python task exceeded timeout…`. The input limit matters more than
it looks: a large API response or a long `conversation_history` in state counts towards it. The
return value must be JSON-serialisable plain data: strings, numbers, booleans, `None`, lists and
dicts.

## Guarding against missing state

Use `state.get('k', default)` rather than `state['k']`. A `KeyError` fails the whole run, whereas
a default lets a branch handle the empty case. This matters most on the first node, which sees
only what the caller supplied plus `state_schema` defaults.

## Worked example: does the cheque match what the customer typed?

A payout flow has a `document_extraction` node with `document_name: "CANCELLED_CHEQUE"` and
`output_key: "cheque"`, and an `llm_data_collection` node `payout_details` that collected the
account number in chat. This node compares the two and sets a routing flag:

```python
def run(state):
    typed = _get_or_default(
        "payout_details.results.bank_account_details.values.account_number", "")
    if not _has_classification("CANCELLED_CHEQUE"):
        state["cheque_check"] = "no_cheque"
        return state
    on_cheque = _extraction_by_classification("CANCELLED_CHEQUE", 1).get("account_number") or ""
    typed_digits = re.sub(r"\D", "", str(typed))
    cheque_digits = re.sub(r"\D", "", str(on_cheque))
    state["cheque_check"] = "match" if typed_digits and typed_digits == cheque_digits else "mismatch"
    return state
```

State in, abridged:

```json
{"payout_details": {"verdict": "COMPLETE",
   "results": {"bank_account_details": {"values": {"account_number": "0012 3456 7890"}}}},
 "cheque_1": {"account_number": "001234567890", "ifsc_code": "HDFC0001234"}}
```

State out: the same, plus `"cheque_check": "match"`. Route on it with three `state_key_equals`
edges, `match` / `mismatch` / `no_cheque`, one `value` per edge (see `edges.md`). It is a
top-level key, so `state_key_equals` can read it.
