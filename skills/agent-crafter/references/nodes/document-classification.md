# `document_processing` / `document_classification`

Vision-LLM node that buckets the files attached to a run. `document_processing` configs are
**flat**, and the discriminator lives under `document_processing_type` — not `subtype`.

```json
{"node_type": "document_processing", "document_processing_type": "document_classification",
 "llm_id": "gpt-4o",
 "max_tokens": 1000,
 "classification_mode": "DEFAULT_CLASSIFICATION",
 "categories": [
   {"name": "POLICY_COPY",   "description": "An insurance policy document"},
   {"name": "BANK_STATEMENT","description": "A bank account statement"}]}
```

`llm_id` must be a **vision-capable** model. `classification_mode` is `DEFAULT_CLASSIFICATION`;
`DES_CLASSIFICATION` is a declared seam that is not implemented, so do not use it.

## Where files come from

Files arrive with the run (the session run body's `files` list — file-service ids or URLs, capped
at 20). You do not fetch them. The node processes files currently bucketed `NOT_PROCESSED`,
writes the verdict back to each `FileExtraction` row, and refreshes `file_details` in state so
downstream nodes and edge conditions can route on it. A file it cannot classify lands in
`UNCLASSIFIED`.

## Categories

`name` is the bucket, and `document_extraction` refers to it by exactly that string via
`document_name` — so keep names stable and machine-ish (`POLICY_COPY`, not `Policy copy`).
`description` is what the model actually reasons over, so make it discriminative: say what
distinguishes this document from its neighbours, not just what it is.

## Failure behaviour is lenient, on purpose

One unreadable file marks its own row `FAILED` and the run continues, because the other files may
still classify fine. Only a config error — no categories, a bad mode, no usable LLM — fails the
run outright. This is the opposite of `document_extraction`; see that file for why.

PDFs are rasterised to PNG. Downloads are capped at 25 MiB and streamed, so an oversized file
aborts mid-transfer rather than buffering into memory.
