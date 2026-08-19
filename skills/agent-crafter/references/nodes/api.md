# `communication` / `api`

Outbound HTTP. This is a side-effect node: it calls out and writes the response to `output_key`.

```json
{"node_type": "communication", "communication_type": "api",
 "api": {
   "host_config_key": "PARTNER_API_HOST",
   "path": "v1/tickets/classify",
   "method": "POST",
   "headers": {"Content-Type": "application/json"},
   "body_template": "{\n  \"ticketId\": \"{{state.ticketId}}\",\n  \"classification\": \"{{state.classification.category}}\"\n}",
   "output_key": "classify_api_result",
   "process_non_2xx": false}}
```

`communication` configs also carry `kafka` and `rabbitmq_message` sub-dicts — leave them at
defaults. `communication_type` must be `api`.

## The URL is not freeform

It is built from `host_config_key` + `path`. `host_config_key` names an **environment variable**,
and only keys listed in `node_catalog().host_config_keys` are permitted — this is an SSRF
allowlist, so an arbitrary host is rejected by design. Pick the key from the catalog; never
invent one.

Older payloads still carry a `url` key alongside. It is ignored; do not rely on it or copy it
into new nodes.

## Templates and `${KEY}`

`body_template` is Jinja2 over state. Use `{{message | tojson}}` when interpolating text into a
JSON body — it escapes quotes and newlines that would otherwise produce invalid JSON.

Separately, `${KEY}` references inside `path` and `headers` (not `body_template`) resolve from
env config **first**, then fall back to runtime `state`. That fallback is deliberate but
double-edged: a state key sharing a name with a config key gets injected into your URL or
headers. Name config references distinctly — `PARTNER_API_KEY`, not `token`.

## Method and failures

`GET` and `HEAD` never carry a JSON body regardless of `body_template`. With
`process_non_2xx: false` a non-2xx response fails the run; set it `true` when you want to inspect
the status in a downstream node instead of aborting.

Because this node has real side effects, put it *after* the decision that justifies it, not
before — a misrouted graph that has already filed a ticket cannot be undone by fixing the edge.
