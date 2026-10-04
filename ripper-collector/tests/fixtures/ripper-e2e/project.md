# Ripper E2E Scheduler

The project coordinates a DAG of tasks, persists task state, retries transient
failures with bounded backoff, and recovers workers through heartbeat leases.

The test document exists only to verify the installed Collector command chain.
