# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [SemVer](https://semver.org/).

## [0.1.0.dev0] — 2026-10-01

First pre-release, trained on the seed dataset (not for production).

### Added
- Library `sikaguard`: `analyze()`, `Analyzer` with tunable thresholds, three verdicts,
  six scam categories, exact explanations and advice.
- Anti-evasion normalization (look-alike letters, leetspeak, spaced letters,
  zero-width characters, emojis) and PII masking shared by dataset and inference.
- 15 expert signals and link inspection (shorteners, IP hosts, suspicious TLDs,
  brand look-alikes, homograph links).
- Secure model persistence: `skops`, SHA-256 manifest, type allow-list.
- CLI `sikaguard`, REST API (`sikaguard[api]`), Docker image, Gradio demo.
- Dataset tooling: schema validation, anonymization checks, near-duplicate grouping,
  grouped stratified split; seed dataset of 407 SMS; annotation guide, datasheet,
  model card.
- Evaluation: 5-model benchmark, bootstrap CIs, operating point, hard-negative and
  per-category analysis, adversarial robustness with a normalization ablation.

### Fixed during development (found by the test suites)
- Letters spaced across two words (`c o d e s e c r e t`) were joined into one
  unknown word; they are now re-segmented (behavioral tests).
- Links written with Cyrillic look-alike letters escaped link detection; letters are
  now folded first and such links are flagged as homograph attacks (robustness
  evaluation, run 1: 80.6 % → run 2: 91.7 % under the look-alike disguise).
