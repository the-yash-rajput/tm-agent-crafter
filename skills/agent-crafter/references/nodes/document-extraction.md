# `document_processing` / `document_extraction`

Vision-LLM node that pulls named fields out of already-classified files. Config is **flat**,
discriminated by `document_processing_type`.

```json
{"node_type": "document_processing", "document_processing_type": "document_extraction",
 "llm_id": 3,
 "max_tokens": 1000,
 "document_name": "POLICY_COPY",
 "fields": [
   {"name": "policy_number", "description": "The policy number, usually top-right"},
   {"name": "insured_name",  "description": "Full name of the insured person"}],
 "output_key": "policy_copy"}
```

`llm_id` is the integer id of an **AzureOpenAI**, vision-capable LLM row. Any other provider fails
the run with `Provider '…' does not support vision document processing`.

## It runs after classification

`document_name` must match a `name` from an upstream `document_classification` node's
`categories` exactly — that is how it selects which files to read. A typo yields
`No file classified as '<name>'` and a failed run, so wire the two nodes with the same constant.

## Output: one numbered key per file

The node reads **every** file in the `document_name` bucket, not just the first. Each result
lands at `<output_key>_1`, `<output_key>_2`, … in bucket order. A single file still lands in
`_1`. **There is no bare `<output_key>`**, so `{{state.policy_copy.policy_number}}` is always
empty. Write `{{state.policy_copy_1.policy_number}}`.

A blank `output_key` defaults to `<DOCUMENT_NAME>_extraction_result`, with non-alphanumerics
collapsed to `_`. So `"PAN CARD"` gives `PAN_CARD_extraction_result_1`. Set `output_key`
explicitly so the keys downstream nodes read cannot drift with a document rename. None of these
keys need a `state_schema` entry.

The index is the file's **position in the bucket**, not a running count. A skipped file leaves
its slot empty, so `_1` may be absent while `_2` exists. That keeps the keys in step with the
sandbox helper `_extraction_by_classification("POLICY_COPY", 2)`, which indexes the same bucket.
In `python_inline` code or a `python_expression` edge, prefer the helpers over hand-built key
names: check `_has_classification(...)` first, since `_extraction_by_*` raise when nothing
matches. See `python-inline.md`.

## Fields

`description` does the real work — it is the instruction the model follows. Say where the value
appears and what it looks like ("13-digit number, top-right of page 1") rather than restating the
field name. Vague descriptions are the main cause of wrong extractions. A field the model cannot
find comes back empty, and a stored `{}` (none of the fields found) still counts as an answer.

## Paying for each file once

- Results are written back to the file's `FileExtraction` row and `file_details` is refreshed.
  A later run reuses a stored extraction instead of calling the model again.
- **Identical uploads cost one vision call.** The node stores an MD5 of each downloaded file. A
  re-upload of the same bytes in the same session reuses the earlier answer, provided that answer
  has exactly this node's `fields`. The duplicate still gets its own slot (`_2`), and its row's
  comment reads `extracted in-house (reused from <row id>)`.

## Failure behaviour is strict, on purpose

Downstream nodes read these keys by name, so a file that fails here, even one out of several,
returns `_error` and fails the run rather than continuing against a missing key. Files
extracted before it keep their results, so a re-run does not pay for them again. That
asymmetry with `document_classification` is deliberate: a half-finished classification is still
useful, a missing extraction result is not.

The bucket is per session and only grows, so strictness is bounded:

| Case | Behaviour |
|---|---|
| Row already failed **by the crafter** in an earlier run (comment starts `in-house: `) | skipped, not retried. Recovery is a re-upload, which arrives as a new row |
| Row failed by DES (turtle-doc) with a known type | gets **one** crafter retry |
| Download fails 4xx (gone, forbidden, bad id), 408/429 excepted | permanent: row marked failed, later runs skip it |
| Download fails 5xx, connect error or timeout | transient: row left retryable |
| Unreadable file or non-JSON model reply | permanent: row marked failed |
| Every file in the bucket dead | no keys produced, so `_error` saying exactly that |

Config errors also fail the run: no `document_name`, no `fields`, or no usable LLM.

## Worked example: read the cancelled cheque

Upstream, a `document_classification` node has a `CANCELLED_CHEQUE` category. The customer
uploads one cheque photo.

```json
{"name": "read_cheque", "type": "document_processing", "subtype": "document_extraction",
 "config": {"node_type": "document_processing", "document_processing_type": "document_extraction",
            "llm_id": 3, "max_tokens": 1000,
            "document_name": "CANCELLED_CHEQUE",
            "fields": [
              {"name": "account_holder", "description": "Name printed above the signature line"},
              {"name": "account_number", "description": "Account number, digits only, keep leading zeros"},
              {"name": "ifsc_code", "description": "11-character IFSC, e.g. HDFC0001234"},
              {"name": "bank_name", "description": "Bank name from the cheque's top-left logo or header"}],
            "output_key": "cheque"}}
```

State after the node:

```json
{"cheque_1": {"account_holder": "RAHUL SHARMA", "account_number": "001234567890",
              "ifsc_code": "HDFC0001234", "bank_name": "HDFC Bank"}}
```

Put an edge guard *before* this node so it only runs when a cheque arrived. Without one, a turn
with no cheque fails the run on `No file classified as 'CANCELLED_CHEQUE'`. `python_expression`
edges run in the same sandbox as `python_inline`, so the helpers work there:

```json
{"condition_type": "python_expression",
 "python_expression": {"expression": "_has_classification('CANCELLED_CHEQUE')"}}
```

Pair it with the exact negation, `not _has_classification('CANCELLED_CHEQUE')`, on the edge that
asks the customer for the cheque.
