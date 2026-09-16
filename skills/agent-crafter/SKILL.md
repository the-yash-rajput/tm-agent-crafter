---
name: agent-crafter
description: Build, edit, validate, run and debug Agent Crafter LangGraph workflow agents through the tm-agent-crafter MCP tools. Use this whenever the user wants to create an agent or workflow, add or change a node or an edge, wire up an LLM/Python/API/RAG/Kafka/RabbitMQ/document step, pause a workflow and pick it up later, collect required fields or documents from a customer over multiple turns, understand why an agent returned the wrong answer or failed a run, or copy an existing agent into a new version. Trigger on "agent crafter", "build an agent", "create a workflow", "add a node", "add a branch", "collect details until complete", "ask until I have everything", "wait an hour then follow up", "why did my agent fail", "run my agent", even when the user never says the words "agent crafter".
---

# Agent Crafter

Agent Crafter builds LangGraph workflows as graphs of typed nodes, driven through the
`tm-agent-crafter` MCP tools.

**An agent is one JSON document, not a sequence of API calls.** Nodes and edges live inside
that document and edges reference nodes *by name*, so you author the whole graph at once and
send it in a single `create_agent` call. That is why there are 8 tools instead of 25.

## Plan and agree before you build

A request like "build me an agent that handles refund tickets" is a sentence; the agent is a
business process. Going straight to `create_agent` means guessing at the parts the user holds in
their head, and guessing wrong is expensive here — nodes have real side effects (tickets filed,
messages published, APIs called), and a wrong graph shape usually means rebuilding rather than
patching.

So unless the request is already unambiguous, do this first:

1. **Ask what you cannot infer.** Keep it to the few answers that actually change the graph:
   - What triggers it, and what arrives in state on turn one?
   - What are the decision points, and what are *all* the outcomes at each — including the
     "none of the above" case?
   - What should happen at each ending: reply only, or a side effect (ticket, message, API call)?
   - Is it one-shot or multi-turn? Multi-turn needs an `is_session_id` key.
   - Is anything being *gathered* — a set of fields or documents the agent chases until it has
     them all? That is `llm_data_collection` plus a loop back, not a hand-written prompt and a
     tally node.
   - Which steps genuinely need an LLM, and which are deterministic? Prefer `python_inline`
     wherever the logic is expressible in code — it is free, fast and cannot hallucinate.
2. **Show the plan in plain language**, before writing any JSON: the node list with each node's
   type and job, the branches with their conditions, and what lands in state. A five-line sketch
   is enough. This is where the user catches a missing branch, and catching it here costs
   nothing.
3. **Get agreement, then build.** Once they confirm, go through the loop below without stopping
   to re-ask.

Ask in one batch rather than one question at a time — a single round of three or four questions
respects the user far more than an interrogation. If they say "just build something" or the task
is genuinely trivial, skip ahead and state the assumptions you made instead, so they can correct
you after seeing something concrete.

## The loop

1. `node_catalog()` — **always first.** Returns every node type with its real `default_config`,
   the LLMs on this instance (you need a concrete `llm_id`), edge condition types,
   `host_config_keys` for `api` nodes, Chroma collections for `rag` nodes.
2. Check the agent library for prior art → `references/library.md`.
3. Author the payload → `references/payload.md`, plus the per-node file for each node you add.
4. `create_agent(payload)` → read the returned `key`. The key is regenerated from the name, so
   whatever you put in the payload is ignored. Status is always `draft`.
5. `validate_agent(key)` → fix `errors`, repeat. Costs no LLM tokens, so run it every time.
6. `run_agent(key, message="...")` → returns `status` and `state_snapshots`.
7. Save the payload back to the library.

Editing: `get_agent(key)` → edit the JSON → `update_agent(key, "1.1.0", edited)`. Versions are
immutable; you never edit one in place, you create the next at a higher semver.

## Where to look things up

Read only what the task needs — these files are here so you don't carry all of it at once.

| Reading | File |
|---|---|
| Envelope, `state_schema`, versioning, the key/name rules | `references/payload.md` |
| `direct` vs `conditional`, `condition_config`, branch coverage | `references/edges.md` |
| A run failed or answered wrong | `references/debugging.md` |
| Finding/reading/writing the shared agent library | `references/library.md` |

One file per node type. Read the one you are about to write:

| Node | File | Use for |
|---|---|---|
| `llm` / `llm_chat` | `references/nodes/llm-chat.md` | one LLM call |
| `llm` / `llm_agent` | `references/nodes/llm-agent.md` | tool-using agent, structured JSON output |
| `llm` / `llm_data_collection` | `references/nodes/data-collection.md` | collect a checklist of fields/documents over multiple turns |
| `functional` / `python_inline` | `references/nodes/python-inline.md` | sandboxed Python |
| `functional` / `agent_call` | `references/nodes/agent-call.md` | call another agent as a sub-graph |
| `functional` / `rag` | `references/nodes/rag.md` | retrieve from Chroma |
| `functional` / `wait` | `references/nodes/wait.md` | pause the run, resume automatically after a delay |
| `communication` / `api` | `references/nodes/api.md` | outbound HTTP |
| `communication` / `rabbitmq_message` | `references/nodes/rabbitmq.md` | publish to RabbitMQ |
| `communication` / `kafka` | `references/nodes/kafka.md` | publish to Kafka |
| `document_processing` / `document_classification` | `references/nodes/document-classification.md` | bucket uploaded files |
| `document_processing` / `document_extraction` | `references/nodes/document-extraction.md` | pull fields out of a classified file |

## The one trap that breaks every node type

`llm` and `document_processing` configs are **flat**. `functional` and `communication` configs
carry a **sub-dict for every sibling subtype**, and the live one is chosen by a discriminator
key. Set the discriminator and fill the matching sub-dict, or the node silently runs as the
wrong kind.

| type | discriminator | must equal |
|---|---|---|
| `llm` | `llm_type` | the subtype |
| `functional` | `function_type` | the subtype |
| `communication` | `communication_type` | the subtype |
| `document_processing` | `document_processing_type` | the subtype |

`node_type` is also in every config and equals `type`. `llm_call` is an accepted alias for
`type: "llm"` in older payloads; write `llm` in new work.

Every node writes its result to `output_key`. Declare that key in `state_schema` or downstream
nodes and edge conditions cannot read it.
