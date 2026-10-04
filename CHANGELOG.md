# Changelog

This changelog records changes to the complete Ripper Skill bundle. The root
`VERSION` file is the authoritative bundle version. Claim revisions and storage
schema versions are managed separately.

## [0.1.0] - 2026-10-04

Initial version prepared for public release. Early-stage personal workflow;
GitHub publication and a release tag have not yet been created.

### Added

- One user-facing Skill routing project deposits, updates, queries, human
  confirmations, exports and recovery through supporting modules.
- Canonical engineering-asset analysis with evidence references, stable claim
  identities, revisions and separate realization and production status.
- Local project archives with source copies, persistent confirmations and
  historical analysis, source and knowledge snapshots.
- A rebuildable SQLite query index, serialized lifecycle operations and
  recovery from interrupted processes.
- Material drafts for interviews, resumes, promotion, yearly reviews, handovers
  and technical writing, with audit manifests and output-hash verification.
- English and Chinese usage documentation, synthetic lifecycle demo,
  deterministic tests, CI configuration and clean source packaging.
- MIT license for Ripper-authored additions and retained third-party notices
  and component/font licenses.

### Known limitations

- Requires a Skill-capable host agent with filesystem and shell access for the
  complete workflow; the CLI does not independently perform LLM analysis.
- Deterministic draft rendering uses templates and keyword/status ranking;
  analysis and editing quality depend on the host agent.
- Designed for personal local use. Multi-user operation and all host/platform
  combinations have not been validated; the new CI has not yet run on GitHub.
- Recovery covers process interruption, not disk failure or full power-loss
  durability. Local storage does not imply local model inference.
