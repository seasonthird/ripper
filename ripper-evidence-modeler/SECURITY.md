# Security Policy

Ripper Evidence Modeler is a prompt and reference-content repository. It does not run services or process data by itself, but it is often used with private codebases, resumes, work notes, and project histories. Treat privacy and confidentiality as part of the security model.

## Supported Versions

The latest version on the default branch is the supported version.

## Sensitive Information

Do not include any of the following in public issues, pull requests, examples, or test prompts:

- API keys, tokens, passwords, cookies, or credentials.
- Private repository URLs or internal service domains.
- Customer names or confidential business relationships.
- Unreleased project names or sensitive architecture details.
- Personal contact information, salary details, or identity documents.
- Full private resumes or work records without redaction.

## Reporting a Vulnerability

If you find a security or privacy issue:

1. Use GitHub's private vulnerability reporting feature if it is enabled.
2. If private reporting is unavailable, contact the maintainers through the repository's preferred private channel.
3. If you must open a public issue, describe the issue at a high level and do not include sensitive examples.

Useful reports include:

- Which file or rule creates the risk.
- Why the behavior is unsafe.
- A minimal redacted example.
- A suggested safer wording or rule.

## Privacy-Oriented Contributions

Security improvements are welcome, especially changes that:

- Reduce over-disclosure of internal project details.
- Improve redaction guidance.
- Prevent fabricated or unsupported resume claims.
- Make evidence boundaries clearer.
