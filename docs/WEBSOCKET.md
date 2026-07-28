# WebSocket telemetry

The backend publishes live drone telemetry through Flask-SocketIO under the
`telemetry` event. Clients first connect, receive `connected`, then emit
`start_telemetry` to subscribe. They can stop delivery with `stop_telemetry`.
Disconnected clients are removed automatically.

After successful drone initialization, the existing `TelemetryServiceAPI`
starts its existing `TelemetryCollector` once in a SocketIO background task.
Each collector snapshot is converted with `to_dict()`, verified as JSON data,
and sent only to subscribed SocketIO client IDs. Delivery is capped at 10 Hz.

If the telemetry service has not been initialized, `start_telemetry` returns a
`telemetry_error` event instead of failing the SocketIO connection. This module
does not publish mission-progress or failsafe events.
