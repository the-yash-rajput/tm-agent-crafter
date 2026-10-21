# `communication` / `kafka`

> **Not implemented: this node publishes nothing.** The runner is a stub. It renders the key and
> payload, writes a receipt to `output_key` and logs `kafka_noop … (stub — not published)`. No
> broker is contacted, and `bootstrap_servers` is never read. Do not use it for anything that must
> reach another system. Use an `api` node to an allowlisted host instead, and tell the user the
> event they asked for will not actually be emitted.

```json
{"node_type": "communication", "communication_type": "kafka",
 "kafka": {
   "bootstrap_servers": "localhost:9092",
   "topic": "payout.events",
   "key_template": "{{state.ticketId}}",
   "payload_template": "{\"ticketId\": {{state.ticketId | tojson}}, \"status\": {{state.classification.category | tojson}}}",
   "output_key": "kafka_result"}}
```

`communication_type` must be `kafka`; leave the sibling `api` and `rabbitmq_message` sub-dicts at
their defaults. The node is hidden from the frontend (`show_in_frontend: false`), so it only
turns up in imported or API-authored payloads.

## What it writes

With `ticketId: "T-1001"` and `classification.category: "refund"`, the node adds:

```json
{"kafka_result": {"status": "queued_locally", "transport": "kafka",
                  "target": "payout.events:T-1001",
                  "payload": {"ticketId": "T-1001", "status": "refund"}}}
```

`target` is `topic:key`, or just `topic` when `key_template` renders empty. `status:
"queued_locally"` is constant. It does not mean anything was queued anywhere. A run that
"published" through this node and succeeded has still sent nothing.

If an existing agent relies on this node, say so when you debug it. The fix is a real transport
(an `api` node), not a change to this config.
