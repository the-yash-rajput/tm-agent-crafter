# `communication` / `rabbitmq_message`

Publishes a message to RabbitMQ. Fire-and-forget side effect; the publish result lands in
`output_key`.

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
their defaults.

Publish either to an `exchange` with a `routing_key`, or directly to a `queue` — set the pair you
actually use and leave the other empty. Getting this wrong publishes successfully into nowhere,
which looks like success in `state_snapshots`.

`payload_template` is Jinja2 and must render to valid JSON. Pipe every interpolated value through
`| tojson` — it quotes and escapes correctly, whereas bare `{{...}}` breaks the moment a value
contains a quote, newline or non-ASCII character.

This node is hidden from the frontend by default (`show_in_frontend: false`), so it appears in
payloads more often than in the UI. Like any side-effect node, place it after the decision that
justifies it — a published message cannot be recalled by fixing an edge.
