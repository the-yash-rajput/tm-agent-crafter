# `document_processing` / `document_classification`

Vision-LLM node that buckets the files attached to a run. `document_processing` configs are
**flat**, and the discriminator lives under `document_processing_type` — not `subtype`.

```json
{"node_type": "document_processing", "document_processing_type": "document_classification",
 "llm_id": 3,
 "max_tokens": 1000,
 "classification_mode": "DEFAULT_CLASSIFICATION",
 "categories": [
   {"name": "POLICY_COPY",   "description": "An insurance policy document"},
   {"name": "BANK_STATEMENT","description": "A bank account statement"}]}
```

`llm_id` is the integer id of an **AzureOpenAI**, vision-capable LLM row. Any other provider fails
the run. `classification_mode` is `DEFAULT_CLASSIFICATION`. `DES_CLASSIFICATION` is a declared
seam that is not implemented, so do not use it.

The node has no `output_key`. Its result is the refreshed `state["file_details"]`.

## Where files come from

Files arrive with the run: the session run body's `files` list holds file-service ids or URLs,
**at most 20 per turn**, and you do not fetch them yourself. Supported content is images (JPG,
JPEG, PNG, WEBP, GIF, BMP, TIF, TIFF) and PDF. **Only the first 3 PDF pages** are rasterised and
sent to the model. Anything else fails with `unsupported file type`. Downloads are capped at
25 MiB and streamed, so an oversized file aborts mid-transfer instead of buffering into memory.

`file_details` covers **every upload in the session**, not just this turn's. A cheque sent on
turn 1 is still in its bucket on turn 5.

## Buckets

The node classifies only files bucketed `NOT_PROCESSED`, writes the verdict back to each
`FileExtraction` row, and refreshes `file_details`:

```json
{"file_category": {"CANCELLED_CHEQUE": ["4ed30d56-…"], "UNCLASSIFIED": ["9a1f…"]},
 "file_records": {"4ed30d56-…": {"classification": "CANCELLED_CHEQUE", "extraction": null}}}
```

A file the model cannot place lands in `UNCLASSIFIED`. Route on buckets with the sandbox helpers,
in a `python_expression` edge or a `python_inline` node: `_has_classification("FIR_COPY")`,
`_files_by_classification("FIR_COPY")`. See `python-inline.md`.

## Shared with the DES pipeline

On a ticket that turtle-doc (DES) has also processed, `file_details` includes DES's rows too.
They are bucketed like this:

| DES row | Bucket |
|---|---|
| still awaiting the DES callback | `IN_PROGRESS`. Never touched, because classifying it would hang the DES chain |
| failed with no or unknown classification, or `UNKNOWN_DOCUMENT` | `NOT_PROCESSED`, so this node retries it **once** |
| failed with a known type (a DES *extraction* failure) | its type. Not reclassified, and `document_extraction` retries it once |
| the crafter's retry also failed (comment starts `in-house: `) | `UNCLASSIFIED`, never retried again |

When a flow mixes DES-classified and crafter-classified files, name your categories after DES's
type keys (`PAN_CARD`, …) so both land in one bucket.

## Categories

`name` is the bucket, and `document_extraction` refers to it by exactly that string via
`document_name` — so keep names stable and machine-ish (`POLICY_COPY`, not `Policy copy`).
`description` is what the model actually reasons over, so make it discriminative: say what
distinguishes this document from its neighbours, not just what it is.

## Identical uploads cost one vision call

Each downloaded file's MD5 is stored. A re-upload of the same bytes in the same session reuses
the earlier classification, provided that category is one of this node's. The row comment reads
`classified in-house (reused from <row id>)`. The duplicate is still downloaded, because hashing
needs the bytes.

## Failure behaviour is lenient, on purpose

One unreadable file marks its own row failed and the run continues, because the other files may
still classify fine. Only a config error — no categories, a bad mode, no usable LLM — fails the
run outright. This is the opposite of `document_extraction`; see that file for why.

## Worked example: motor claim documents

```json
{"name": "sort_claim_docs", "type": "document_processing", "subtype": "document_classification",
 "config": {"node_type": "document_processing", "document_processing_type": "document_classification",
            "llm_id": 3, "max_tokens": 1000, "classification_mode": "DEFAULT_CLASSIFICATION",
            "categories": [
              {"name": "RC_BOOK", "description": "Vehicle registration certificate: RTO header, registration number, chassis and engine numbers"},
              {"name": "DRIVING_LICENCE", "description": "Indian driving licence card with photo, DL number and vehicle classes"},
              {"name": "FIR_COPY", "description": "Police First Information Report: police station name, FIR number, date, incident narrative"},
              {"name": "REPAIR_ESTIMATE", "description": "Garage estimate listing parts and labour with amounts and a total"}]}}
```

The customer uploads four photos. After the node, `file_details.file_category` holds one id under
each of `RC_BOOK`, `DRIVING_LICENCE` and `REPAIR_ESTIMATE`, and the blurry fourth photo sits under
`UNCLASSIFIED`. Two exactly-negated edges route on the missing FIR:

| Edge to | `expression` |
|---|---|
| `read_fir` (a `document_extraction` node, `document_name: "FIR_COPY"`) | `_has_classification('FIR_COPY')` |
| `ask_for_fir` (an `llm_chat` reply) | `not _has_classification('FIR_COPY')` |

When the customer sends the FIR on the next turn, only the new file is classified, because the
earlier four are no longer `NOT_PROCESSED`. The flow then takes the `read_fir` branch.
