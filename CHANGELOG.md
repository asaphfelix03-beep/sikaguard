# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [SemVer](https://semver.org/).

## [0.1.0.dev1] — 2026-10-01

Second pre-release: first real data, Côte d'Ivoire focus. Still not for production
(no real collected scam SMS yet).

### Added
- **Real legitimate SMS**: reproducible importer of the 88milSMS corpus (CC BY 4.0);
  150 messages for training and a disjoint **external benchmark of 1 000 real SMS**
  (false alarms: 0.6 % [0.2 %, 1.1 %]).
- **Documented campaigns**: 40 reconstructions of 12 real, dated scam campaigns in
  Côte d'Ivoire and Senegal (PLCC, police, Orange CI, press) and 5 official notices as
  hard negatives, each with its source URL.
- Campaign-level grouping (a campaign never straddles train and test) and *consumed*
  test splits (archived in `data/history/`, forced into train).
- Four expert signals: `changement_numero`, `paiement_avance`, `demande_discretion`,
  `installation_application` (APK or app outside official stores).
- External-benchmark, per-source and pre-registered real-SMS objective in the report;
  README consistency test; latency tests.

### Fixed
- Refund notifications no longer trigger the money-request signal.
- OTPs saying "code … pour confirmer le paiement" no longer trigger the code-request signal.

### Changed
- Performance: median latency 31 ms → 4.8 ms, p95 42 ms → 9 ms, batch 1.6 ms per SMS
  (precomputed explainer, one feature extraction per SMS, cached normalization,
  no joblib dispatch).
- Evaluation: all 5 pre-registered objectives met (dev0: 2 of 4). The dev0 test split
  was consumed; see the caveats in `reports/evaluation.md`.

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
