#!/usr/bin/env bash
# Optional operator-owned telemetry endpoint for Ripper Collector.
#
# No upstream backend is bundled. Telemetry remains local unless an operator
# explicitly exports both URL and anon-key variables before running the
# collector. Empty defaults prevent this fork from sending data to the source
# project's infrastructure or assigning its users to another data controller.

: "${RIPPER_COLLECTOR_SUPABASE_URL:=}"
: "${RIPPER_COLLECTOR_SUPABASE_PROJECT_REF:=}"
: "${RIPPER_COLLECTOR_SUPABASE_ANON_KEY:=}"
: "${RIPPER_COLLECTOR_SUPABASE_REGION:=}"
