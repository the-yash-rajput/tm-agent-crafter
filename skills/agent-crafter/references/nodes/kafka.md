# `communication` / `kafka`

Publishes a message to a Kafka topic. Side effect; the result lands in `output_key`.

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
their defaults.

`key_template` sets the partition key. Setting it to a stable identity — a ticket id, a user id —
keeps all events for that entity on one partition and therefore in order. Leave it empty only
when ordering genuinely does not matter.

`payload_template` is Jinja2 and must render to valid JSON. Pipe interpolated values through
`| tojson` so quotes, newlines and unicode cannot produce a malformed message.

Hidden from the frontend by default (`show_in_frontend: false`). As with every side-effect node,
place it downstream of the decision that justifies emitting the event.
