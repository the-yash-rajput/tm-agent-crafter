# `communication` / `api`

Outbound HTTP. This is a side-effect node: it calls out and writes the response to `output_key`.

```json
{"node_type": "communication", "communication_type": "api",
 "api": {
   "host_config_key": "PARTNER_API_HOST",
   "path": "v1/tickets/classify",
   "method": "POST",
   "headers": {"Content-Type": "application/json"},
   "body_template": "{\n  \"ticketId\": {{state.ticketId | tojson}},\n  \"classification\": {{state.classification.category | tojson}}\n}",
   "output_key": "classify_api_result",
   "process_non_2xx": false}}
```

`communication` configs also carry `kafka` and `rabbitmq_message` sub-dicts — leave them at
defaults. `communication_type` must be `api`. Defaults when a key is omitted: `method` `POST`,
`output_key` `api_result`, `process_non_2xx` `false`.

## The URL is not freeform

It is built from `host_config_key` + `path`. `host_config_key` names an **environment variable**,
and only keys listed in `node_catalog().host_config_keys` are permitted — this is an SSRF
allowlist, so an arbitrary host is rejected by design. Pick the key from the catalog; never
invent one. A blank key fails with `API node requires a host_config_key`, and a key that is not
set on this deployment fails with `Host config key '…' is not set in environment`.

`path` is rendered against state, so `/tickets/{{state.ticket_id}}/comments` works. Older
payloads still carry a `url` key alongside; it is ignored, so do not copy it into new nodes.

## Templates and `${KEY}`

`body_template` is Jinja2 over state and should render to JSON. Pipe interpolated values through
`| tojson` — it quotes and escapes correctly, whereas `"{{state.name}}"` breaks the moment a value
contains a quote or newline. A body that does not parse as JSON is sent as a JSON string, which
the receiver will probably reject.

Separately, `${KEY}` references inside `path` and `headers` (not `body_template`) resolve from
env config **first**, then fall back to runtime `state`. That fallback is deliberate but
double-edged: a state key sharing a name with a config key gets injected into your URL or
headers. Name config references distinctly — `PARTNER_API_KEY`, not `token`. Never paste a
secret into `headers` directly. A `headers` value that does not render to a valid name/value map
fails the run with `API node headers misconfigured`, rather than sending the request without them.

## Method, timeouts and failures

- `GET` and `HEAD` never carry a body, whatever `body_template` says.
- Every call times out after **30 seconds** (`API request timed out after 30s`), and redirects are
  **not** followed.
- With `process_non_2xx: false` (default), a non-2xx response fails the run, and on success
  `output_key` holds the parsed JSON body (or the raw text if it is not JSON).
- With `process_non_2xx: true`, every response is wrapped so a downstream edge can branch on it:

```json
{"status_code": 404, "ok": false, "body": {"error": "policy not found"}}
```

Because this node has real side effects, put it *after* the decision that justifies it, not
before — a misrouted graph that has already filed a ticket cannot be undone by fixing the edge.

## Worked example: policy lookup where "not found" is a normal answer

```json
{"name": "lookup_policy", "type": "communication", "subtype": "api",
 "config": {"node_type": "communication", "communication_type": "api",
            "api": {"host_config_key": "MIS_HOST", "path": "/api/policy/search", "method": "POST",
                    "headers": {"Content-Type": "application/json", "Authorization": "Bearer ${MIS_API_KEY}"},
                    "body_template": "{\"vehicle_number\": {{state.identifier_extraction.vehicle_number | tojson}}}",
                    "output_key": "mis_result", "process_non_2xx": true}}}
```

Found: `mis_result: {"status_code": 200, "ok": true, "body": {"policy_number": "P123", "status": "ISSUED", "dp_id": "DP-42"}}`.
Not found: `mis_result: {"status_code": 404, "ok": false, "body": {…}}`, and the run carries on.

| Edge to | `expression` |
|---|---|
| `check_ownership` | `state.get('mis_result', {}).get('ok', False)` |
| `escalate` | `not state.get('mis_result', {}).get('ok', False)` |

Downstream, read the fields through `body`: `{{state.mis_result.body.status}}`. With
`process_non_2xx` off, the same field is `{{state.mis_result.status}}`. Changing that flag moves
every field one level down, so update the readers when you flip it.
