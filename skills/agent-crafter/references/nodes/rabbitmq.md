# `communication` / `rabbitmq_message`

> **Not implemented: this node publishes nothing.** The runner is a stub. It renders the payload,
> writes a receipt to `output_key` and logs `rabbitmq_message_noop … (stub — not published)`.
> `host`, `port` and `exchange` are never used to connect. Do not use it for anything that must
> reach another system. Use an `api` node to an allowlisted host instead, and tell the user the
> message they asked for will not actually be sent.

```json
{"node_type": "communication", "communication_type": "rabbitmq_message",
 "rabbitmq_message": {
   "host": "localhost",
   "port": 5672,
   "exchange": "",
   "routing_key": "payout.classified",
   "queue": "",
   "payload_template": "{\"ticketId\": {{state.ticketId | tojson}}, \"category\": {{state.classification.category | tojson}}}",
   "output_key": "rabbitmq_result"}}
```

`communication_type` must be `rabbitmq_message`; the sibling `api` and `kafka` sub-dicts stay at
their defaults. The node is hidden from the frontend (`show_in_frontend: false`), so it only
turns up in imported or API-authored payloads.

This is unrelated to how agents are *invoked* over RabbitMQ: the ticket integrations that run
agents and receive their replies over queues work fine. Only this node, publishing from inside a
graph, is a stub.

## What it writes

With `ticketId: "T-1001"` and `classification.category: "refund"`, the node adds:

```json
{"rabbitmq_result": {"status": "queued_locally", "transport": "rabbitmq_message",
                     "target": "payout.classified",
                     "payload": {"ticketId": "T-1001", "category": "refund"}}}
```

`target` is the first non-empty of `routing_key`, `queue`, `exchange`. `status:
"queued_locally"` is constant. It does not mean anything was queued anywhere. A run that
"published" through this node and succeeded has still sent nothing.
