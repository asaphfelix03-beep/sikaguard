# Security policy

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub's private reporting:
<https://github.com/asaphfelix03-beep/sikaguard/security/advisories/new>.

You will get an acknowledgement within 7 days. Please include the version, a
description of the impact and steps to reproduce.

## Scope

In scope:

- the `sikaguard` package and its REST API (e.g. a crafted input that crashes the
  service, leaks SMS text into logs, or bypasses input limits);
- model loading (a crafted model file that executes code despite the SHA-256 and
  type allow-list checks);
- the anonymization functions (`sikaguard.pii`) leaking personal data into the dataset.

**Evasions** (a scam that the model misses, e.g. a new disguise) are welcome as normal
issues: they are improvements to the detector, not vulnerabilities.

## Supported versions

Only the latest release receives fixes. `0.1.0.dev0` is a pre-release.
