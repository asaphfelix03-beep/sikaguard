# Model card — sikaguard `0.1.0.dev0`

Following *Model Cards for Model Reporting* (Mitchell et al., 2019).

## Model details

| | |
|---|---|
| Developer | Ojewumi Asaph Felix |
| Version | `0.1.0.dev0`, flagged **not for production** in `manifest.json` |
| Date | 2026-09-30 |
| Type | Two-stage linear classifier (scikit-learn logistic regression) |
| Stage 1 | Binary scam score: character 2–5-grams + word 1–2-grams (TF-IDF, sublinear) + 15 binary expert signals; `C = 10`, balanced class weights |
| Stage 2 | Scam category (6 classes), same features, trained on scams only; called when the verdict is not `legitime` |
| Decision | `arnaque` if score ≥ 0.421, `legitime` if score < 0.161, otherwise `suspect` |
| Serialization | `skops` (no pickle), SHA-256 in `manifest.json`, explicit type allow-list |
| Size / speed | ~0.7 MB; CPU only |
| License | MIT |
| Contact | GitHub issues of the repository |

## Intended use

- **Primary use:** decision support. It warns a person, or a developer's application,
  that an SMS written in French looks like a scam, explains why and gives advice.
- **Primary users:** developers of fintech, messaging, or consumer-protection tools in
  francophone West Africa; researchers working on low-resource scam detection.
- **Out of scope:**
  - blocking or deleting messages automatically without a human in the loop;
  - languages other than French (English, Wolof, Dioula, Nouchi mixes are not covered);
  - legal evidence, or judging a person or a phone number;
  - any production use of this `0.1.0.dev0` version, which is trained on seed data.

## Training and evaluation data

The seed dataset (`data/seed/seed_sms.csv`, 407 SMS: 177 scams in 6 categories and 230
legitimate messages in 4 categories) was **written by hand by the author** from publicly
documented scam patterns and the format of operator notifications. It contains
deliberate hard negatives: legitimate messages that mention secret codes, blocked
accounts, urgency, prizes or money requests between relatives. See the
[datasheet](datasheet.md).

Split: 80/20 by near-duplicate group (character 5-gram Jaccard ≥ 0.8), stratified by
category: 325 train / 82 test SMS.

## Metrics and results

Selection and thresholds by grouped, stratified 5-fold cross-validation on train;
test split opened once; 95 % percentile bootstrap intervals (1 000 resamples).
Source: [`reports/metrics.json`](../reports/metrics.json).

| Metric (test) | Value |
|---|---|
| Average precision (PR-AUC) | 0.973 [0.935, 0.995] |
| Recall at 95 % precision | 80.6 % [63.2 %, 97.6 %] |
| Precision of the `arnaque` verdict | 88.9 % |
| Scams flagged `arnaque` / `arnaque` or `suspect` | 88.9 % / 91.7 % |
| Legitimate SMS flagged `arnaque` | 8.7 % |
| False positives on hard legitimate SMS (notifications, OTP; n = 22) | 13.6 % |
| Category accuracy / macro-F1 on test scams (n = 36) | 88.9 % / 0.888 |
| Detection after each of 7 disguises (with / without normalization) | 91.7 % for every disguise / down to 61.1 % |

Pre-registered objectives: 2 of 4 met (average precision, robustness); recall at 95 %
precision and false positives on hard legitimate SMS are missed.

**These results are measured on hand-written seed data and must not be read as
real-world performance.**

## Known limitations and failure modes

Observed in the test errors (listed in [`reports/evaluation.md`](../reports/evaluation.md)):

1. **Refund notifications** ("Remboursement de 2 000 F crédité…") trigger the
   *money request* signal, whose vocabulary includes *rembours-*.
2. **OTP messages** containing "code … pour confirmer" trigger the *secret code request*
   signal, because *confirmer* is in the list of "send" verbs.
3. **Polite scams with no red-flag words** (fake sales paid in advance, a relative asking
   to forward money) are missed: the seed data has too few of them.
4. **Personal messages about money** (rent, tontine contributions) can be flagged.
5. The model has never seen real SMS; vocabulary, spelling and code-switching in real
   messages will differ.

Fixes for 1 and 2 are planned in [ROADMAP.md](../ROADMAP.md). They will be validated on
the **new, real-data test split**: tuning them on the current test split would
invalidate it.

## Ethical considerations

- **Privacy:** phone numbers, codes, transaction references and e-mails are masked by
  the same code in the dataset and at inference; the API never logs SMS text; the demo
  stores nothing.
- **Harm from errors:** a false `legitime` may reassure a victim; a false `arnaque` may
  make someone ignore a real notification. Hence three verdicts, advice that always
  points to official channels, and the out-of-scope list above.
- **Bias:** all seed data is written by one person from Côte d'Ivoire's perspective
  (58 % of rows are tagged CI). Other countries, operators and writing styles are
  under-represented.
- **Trademarks:** operator names are used descriptively; no logos; not affiliated.

## How to reproduce

```bash
python -m sikaguard_lab.build && python -m sikaguard_lab.train && python -m sikaguard_lab.evaluate
```
