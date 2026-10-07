# `functional` / `rag`

Answers a question from a ChromaDB collection: it retrieves the most relevant passages, then
writes an answer grounded in them.

```json
{"node_type": "functional", "function_type": "rag",
 "rag": {
   "collection_name": "policy_docs",
   "rag_type": "crag",
   "llm_id": 3,
   "filters": {},
   "top_k": 3,
   "score_threshold": null,
   "input_key": "",
   "output_key": "rag_response"}}
```

`collection_name` must come from `node_catalog().chroma_collections`. If that list is empty,
Chroma is unreachable from the server — the catalog degrades rather than failing, so an empty
list is a real signal, not a glitch. Say so instead of guessing a name. The node cannot add
documents to a collection; ingestion happens outside Agent Crafter.

`llm_id` is the integer id of the LLM row that writes the answer (and, for `crag`, grades the
retrieved passages).

## Settings

| Key | Meaning |
|---|---|
| `input_key` | the state key holding the question. Blank, or a key that is empty at run time, falls back to `message` |
| `rag_type` | `crag` (default — grades passages for relevance before answering), `selfrag` (checks its own answer against the passages), `hyde` (drafts a hypothetical answer and searches with it; helps short or vague questions) |
| `top_k` | how many passages to retrieve. Default 3. More adds context but dilutes the answer |
| `filters` | narrows the search, see below. `{}` searches the whole collection |
| `score_threshold` | drops weak passages. **Only applies in `vector_id` filter mode**; ignored otherwise |
| `output_key` | where the result goes. Default `rag_response` |

## Filters

`filters` is `{"mode": …, "value": …}`:

| `mode` | `value` | Effect |
|---|---|---|
| absent | — | whole collection |
| `"metadata"` | a dict, or a Jinja string that renders to JSON, e.g. `"{\"product\": \"{{state.product}}\"}"` | Chroma metadata filter. An empty value searches everything |
| `"vector_id"` | the **name of a state key** holding a list of chunk ids | searches only those chunks, honouring `score_threshold`. A non-string value is treated as no ids |

## Output

```json
{"generation": "Yes. Windshield damage is covered under the comprehensive policy, subject to …",
 "documents": [{"id": "c-118", "page_content": "Section 3.2 Glass …", "metadata": {"section": "coverage"}}]}
```

When nothing usable is found, `generation` is the literal string `"No answer generated."`. To
route "no answer" differently from "here is an answer", compare against that string with an
exactly-negated pair of `python_expression` edges:

```
state.get('policy_answer', {}).get('generation') != 'No answer generated.'
state.get('policy_answer', {}).get('generation') == 'No answer generated.'
```

## Worked example: policy coverage question

Customer: `"does my policy cover a cracked windshield??"`. A first `llm_chat` node rewrites
the message into a clean question and saves it as `rewritten_question`. Then:

```json
{"name": "search_wordings", "type": "functional", "subtype": "rag",
 "config": {"node_type": "functional", "function_type": "rag",
            "rag": {"collection_name": "motor_policy_wordings", "rag_type": "crag", "llm_id": 3,
                    "filters": {"mode": "metadata", "value": {"product": "motor_comprehensive"}},
                    "top_k": 5, "score_threshold": null,
                    "input_key": "rewritten_question", "output_key": "policy_answer"}}}
```

State after:
`policy_answer: {"generation": "Yes — glass damage is covered …", "documents": [ … 5 passages … ]}`.
A final `llm_chat` turns it into a friendly reply with
`{{state.policy_answer.generation}}` in its `user_prompt_template`. Feeding RAG the rewritten
question rather than the raw chat text is what makes retrieval reliable.
