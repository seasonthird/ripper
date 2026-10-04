# Contributing

Keep the complete bundle together. The unified lifecycle is in `ripper/`;
analysis rules are in the component Skills; deterministic persistence is in
`ripper-core/` and Collector project orchestration.

## Development

Use a separate Python 3.10+ development environment. Do not overwrite another
host or platform's existing `.venv`.

```bash
python3 -m pip install -r ripper-collector/requirements-dev.txt
cd ripper-collector
python3 -m pytest -q -m "not live_llm"
```

Run `python3 tools/demo.py` from the root to exercise the public CLI. Live-model
tests require a locally configured agent and are not part of default CI.

## Changes

Preserve archive-first storage, stable identities, explicit evidence states and
serialized lifecycle operations. Add behavioral regression coverage when changing
persistence, confirmation, recovery or export snapshots. Tests must isolate both
the home/archive root and output directory and use synthetic materials.

Keep English and Chinese README capabilities consistent. Do not add personal
project archives, resumes, internal URLs, credentials, model conversations or
unreviewed screenshots to examples or issue reports. Root CI and package tooling
must work from a clean checkout, without private files or local environment state.

Retain upstream copyrights and license notices. New source files use the root
MIT license unless a separate notice explicitly applies.
