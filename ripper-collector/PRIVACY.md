# Ripper Collector privacy notice

Ripper Collector is local-first. Project archives are stored under
`~/Ripper/archives/`; collector runtime state is stored under
`ripper-output/ripper-collector/`.

## Default behavior

Telemetry defaults to `off`. No remote telemetry endpoint, credential, data
controller, hosted dashboard, or upstream issue tracker is bundled with this
project. A normal installation therefore does not transmit analytics.

The optional telemetry commands are:

```text
ripper-collector telemetry status
ripper-collector telemetry export
ripper-collector telemetry delete
ripper-collector telemetry set-tier off|anonymous|community
```

- `off`: no telemetry event is recorded.
- `anonymous`: whitelisted operational events may be written to the local
  JSONL queue without an installation identifier.
- `community`: the same local events may include a random installation ID.

Choosing `anonymous` or `community` does not by itself configure a remote
destination. Synchronization is enabled only when the operator explicitly
provides both `RIPPER_COLLECTOR_SUPABASE_URL` and
`RIPPER_COLLECTOR_SUPABASE_ANON_KEY`. The operator who configures that endpoint
is responsible for publishing its controller identity, retention policy,
region, deletion behavior, and lawful basis before enabling collection.

## Event boundaries

The optional event schema is limited to operational metadata such as event
type, timestamp, collector version, host, model identifier, duration, outcome,
declared error class, input format, and aggregate counts. It must not contain
resume text, job-description text, project source, file paths, credentials,
names, email addresses, phone numbers, or GitHub usernames.

## Local control

- `telemetry export` prints the local JSONL queue.
- `telemetry delete` removes the local queue and installation ID. If an
  operator-configured endpoint exists, the command also attempts its deletion
  endpoint.
- `telemetry set-tier off` stops future event recording.

Deleting `ripper-output/ripper-collector/` removes collector runtime state but
does not delete project archives under `~/Ripper/archives/`.
