# `functional` / `rag`

Retrieval from a ChromaDB collection.

```json
{"node_type": "functional", "function_type": "rag",
 "rag": {
   "collection_name": "policy_docs",
   "rag_type": "crag",
   "llm_id": "gpt-4o",
   "filters": {},
   "top_k": 3,
   "score_threshold": null,
   "input_key": "",
   "output_key": "rag_response"}}
```

`collection_name` must come from `node_catalog().chroma_collections`. If that list is empty,
Chroma is unreachable from the server — the catalog degrades rather than failing, so an empty
list is a real signal, not a glitch. Say so instead of guessing a name.

`input_key` names the state key holding the query; left blank the node falls back to the
incoming message. `output_key` receives the retrieved answer — declare it in `state_schema`.

`top_k` trades recall against prompt size. `score_threshold` (null = off) drops weak matches,
which is what you want when "no good answer" should route differently from "here is an answer" —
pair it with a conditional edge that checks whether `output_key` came back empty.

`filters` is a metadata filter passed through to Chroma; leave `{}` unless the collection is
known to carry the fields you are filtering on.

`rag_type` defaults to `crag` (corrective RAG, which uses `llm_id` to grade and refine
retrievals). The runner also reads a `mode` key for variant behaviour.
