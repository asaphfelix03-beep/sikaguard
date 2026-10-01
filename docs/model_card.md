# Model card — sikaguard `0.1.0.dev1`

Following *Model Cards for Model Reporting* (Mitchell et al., 2019).
Previous version: [`reports/history/0.1.0.dev0/`](../reports/history/0.1.0.dev0/evaluation.md).

## Model details

| | |
|---|---|
| Developer | Ojewumi Asaph Felix |
| Version | `0.1.0.dev1`, flagged **not for production** in `manifest.json` (no real collected scam SMS yet) |
| Date | 2026-10-01 |
| Type | Two-stage linear classifier (scikit-learn logistic regression) |
| Stage 1 | Binary scam score: character 2–5-grams + word 1–2-grams (TF-IDF, sublinear) + 19 binary expert signals; `C = 30`, balanced class weights |
| Stage 2 | Scam category (6 classes), same features, trained on scams only; called when the verdict is not `legitime` |
| Decision | `arnaque` if score ≥ 0.493, `legitime` if score < 0.108, otherwise `suspect` |
| Serialization | `skops` (no pickle), SHA-256 in `manifest.json`, explicit type allow-list |
| Size / speed | ~1 MB; CPU only; 4.8 ms median / 9 ms p95 per SMS, 1.6 ms per SMS in batches (laptop) |
| License | MIT |

## Intended use

- **Primary use:** decision support. It warns a person, or a developer's application,
  that an SMS written in French looks like a scam, explains why and gives advice.
- **Primary users:** developers of fintech, messaging or consumer-protection tools in
  francophone West Africa, first of all Côte d'Ivoire; researchers on low-resource scam
  detection.
- **Out of scope:**
  - blocking or deleting messages automatically without a human in the loop;
  - languages other than French (English, Wolof, Dioula, Nouchi mixes are not covered);
  - legal evidence, or judging a person or a phone number;
  - production use of this version, which has not seen real collected scam SMS.

## Training and evaluation data

602 SMS ([datasheet](datasheet.md)):

| Source | Rows | Real? |
|---|---|---|
| Seed set, hand-written from documented patterns | 407 (177 scams, 230 legitimate) | no |
| 88milSMS research corpus (France, 2011, CC BY 4.0) | 150 legitimate | **yes** |
| Reconstructions of 12 documented campaigns (CI, SN) + 5 official notices | 40 scams + 5 legitimate | campaigns real, texts reconstructed |

Split 80/20 by group (near-duplicates and campaigns), stratified by category:
498 train / 104 test. The 82 rows of the consumed `0.1.0.dev0` test are in train.
A further **1 000 real 88milSMS messages** are kept out of training as an external
benchmark.

## Metrics and results

Source: [`reports/metrics.json`](../reports/metrics.json).

| Metric | Value |
|---|---|
| **False alarms on 1 000 real SMS** (never seen in training) | **0.6 %** [0.2 %, 1.1 %] flagged `arnaque`; 1.3 % [0.6 %, 2.0 %] `arnaque` or `suspect` |
| Test average precision | 0.997 [0.988, 1.000] |
| Test recall at 95 % precision | 97.2 % [88.9 %, 100 %] |
| Precision of the `arnaque` verdict | 97.2 % |
| Test scams flagged `arnaque` / `arnaque` or `suspect` | 97.2 % / 100 % |
| Hard legitimate SMS flagged `arnaque` (notifications, OTP; n = 17) | 0 % |
| Category accuracy / macro-F1 on test scams (n = 36) | 75.0 % / 0.738 |
| Detection after each of 7 disguises (with / without normalization) | 100 % / down to 88.9 % |

All 5 pre-registered objectives are met. **Caveats:** the test split is close to
saturation because its scams are hand-written or reconstructed; the author of the dev1
changes had read the dev0 errors; the real-SMS benchmark is the least biased number.

## Known limitations

1. **Scam type** is weaker on campaigns never seen in training (75 %): e.g. a fake
   "guaranteed admission" contest offer can be typed `faux_transfert` instead of
   `investissement_emploi`.
2. **Secrecy requests** are only detected in their common forms ("ne prévenez
   personne"); "ne dis rien à papa" is missed.
3. **Fake-authority threats** (fake PLCC agent, fake fines) have no dedicated signal
   yet; they are caught by learned words only.
4. **Commercial operator promotions** ("envoyez de l'argent à moitié prix") can be
   flagged: 2 of 9 test promotions got `suspect` or `arnaque`.
5. **Dialect and era:** real legitimate SMS come from France (2011), while scams are
   West-African; capped at 40 % of the legitimate class, but West-African real SMS
   are still missing.
6. No real collected scam SMS yet.

Planned fixes are in [ROADMAP.md](../ROADMAP.md); they will be validated on a new test
split.

## Ethical considerations

- **Privacy:** phone numbers, codes, references and e-mails are masked by the same code
  in the dataset and at inference; the API never logs SMS text; the demo stores nothing.
- **Harm from errors:** a false `legitime` may reassure a victim; a false `arnaque` may
  make someone ignore a real notification. Hence three verdicts, advice that always
  points to official channels, and the out-of-scope list above.
- **Bias:** the seed set is written by one person; Côte d'Ivoire dominates (46 % of
  rows), other countries are under-represented.
- **Trademarks:** operator names are used descriptively; no logos; not affiliated.

## How to reproduce

```bash
python -m sikaguard_lab.import_88milsms
python -m sikaguard_lab.build --consumed data/history/test_0.1.0.dev0.csv
python -m sikaguard_lab.train && python -m sikaguard_lab.evaluate
```
