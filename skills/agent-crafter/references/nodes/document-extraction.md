# `document_processing` / `document_extraction`

Vision-LLM node that pulls named fields out of an already-classified file. Config is **flat**,
discriminated by `document_processing_type`.

```json
{"node_type": "document_processing", "document_processing_type": "document_extraction",
 "llm_id": "gpt-4o",
 "max_tokens": 1000,
 "document_name": "POLICY_COPY",
 "fields": [
   {"name": "policy_number", "description": "The policy number, usually top-right"},
   {"name": "insured_name",  "description": "Full name of the insured person"}],
 "output_key": "policy_extraction_result"}
```

## It runs after classification

`document_name` must match a `name` from an upstream `document_classification` node's
`categories` exactly — that is how it selects which file to read. A typo here yields nothing to
extract, so wire the two nodes with the same constant.

`llm_id` must be vision-capable. Leaving `output_key` blank defaults it to
`<DOCUMENT_NAME>_extraction_result`; set it explicitly so the name in `state_schema` and the name
downstream nodes read cannot drift apart. Declare it in `state_schema` either way.

## Fields

`description` does the real work — it is the instruction the model follows. Say where the value
appears and what it looks like ("13-digit number, top-right of page 1") rather than restating the
field name. Vague descriptions are the main cause of wrong extractions.

Results are written back to the `FileExtraction` row and `file_details` is refreshed, so a
re-run reuses an already-populated extraction rather than paying for the vision call twice.

## Failure behaviour is strict, on purpose

This node produces exactly one `output_key` that downstream nodes read, so any failure returns
`_error` and fails the run rather than continuing against a missing key. That asymmetry with
`document_classification` is deliberate: a half-finished classification is still useful, a
missing extraction result is not.
