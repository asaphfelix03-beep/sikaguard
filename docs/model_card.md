# Model card — sikaguard `0.1.0.dev2`

Following *Model Cards for Model Reporting* (Mitchell et al., 2019).
Previous versions: [`reports/history/`](../reports/history/).

## Model details

| | |
|---|---|
| Developer | Ojewumi Asaph Felix |
| Version | `0.1.0.dev2`, flagged **not for production** in `manifest.json` (no real West-African scam SMS yet) |
| Date | 2026-10-02 |
| Type | Two-stage linear classifier (scikit-learn logistic regression) |
| Stage 1 | Binary scam score: character 2–5-grams + word 1–2-grams (TF-IDF, sublinear) + 19 binary expert signals; `C = 4`, balanced class weights |
| Stage 2 | Scam category (6 classes), same features, trained on scams only; called when the verdict is not `legitime` |
| Decision | `arnaque` if score ≥ 0.317 (precision ≥ 95 % in cross-validation), `legitime` if score < 0.305 (recall ≥ 99 %), otherwise `suspect` |
| Serialization | `skops` (no pickle), SHA-256 in `manifest.json`, explicit type allow-list |
| Size / speed | ~2 MB; CPU only; 1.8 ms median / 3.1 ms p95 per SMS, 0.6 ms per SMS in batches (laptop) |
| License | MIT |

## Intended use

- **Primary use:** decision support. It warns a person, or a developer's application,
  that an SMS written in French looks like a scam, explains why and gives advice.
- **Primary users:** developers of fintech, messaging or consumer-protection tools in
  francophone West Africa, first of all Côte d'Ivoire; researchers on scam detection.
- **Out of scope:** blocking or deleting messages automatically without a human in the
  loop; languages other than French; legal evidence or judging a person or a number;
  production use in West Africa before real West-African scams are added.

## Training and evaluation data

2 063 SMS, balanced (1 028 scams, 1 035 legitimate). See the [datasheet](datasheet.md).

| Source | Rows | Real? |
|---|---|---|
| IMC'25 smishing dataset (Agarwal et al., ACM IMC 2025, CC BY 4.0): French subset, reviewed by hand | 811 scams | **yes** (victim reports, France / Belgium / Canada) |
| 88milSMS research corpus (France 2011, CC BY 4.0) | 800 legitimate | **yes** |
| Seed set, hand-written from documented West-African patterns | 407 (177 scams, 230 legitimate) | no |
| Reconstructions of 12 documented campaigns (CI, SN) + 5 official notices | 40 scams + 5 legitimate | campaigns real, texts reconstructed |

Human review of IMC'25: 119 of 890 unique French texts excluded (53 legitimate messages,
26 ambiguous, 18 advertising or political, 9 replies of the French 33700 spam service,
8 fragments, 5 not in French); 1 real fake-Mobile-Money credit in FCFA re-typed
`faux_transfert`. Decisions in [`data/sources/review/`](../data/sources/review/).

Split 80/20 by group (near-duplicate templates and campaigns), stratified by category:
1 681 train / 382 test. The test rows of the two previous versions are in train. A
separate external benchmark of **1 000 real 88milSMS messages** is never used for training.

## Metrics and results

Source: [`reports/metrics.json`](../reports/metrics.json). 95 % bootstrap intervals.

| Metric | Value |
|---|---|
| **Real scams detected** (IMC'25 test templates never seen, n = 161) | **99.4 %** [98.1 %, 100 %] |
| **False alarms on 1 000 real personal SMS** (external benchmark) | **0.9 %** [0.4 %, 1.6 %] |
| Average precision, real scams vs real legitimate SMS (test) | 0.9998 [0.9994, 1.000] |
| Test average precision (all sources) | 0.999 [0.998, 1.000] |
| Test recall at 95 % precision | 100 % [98.4 %, 100 %] |
| Precision of the `arnaque` verdict | 97.9 % |
| Hard legitimate West-African SMS flagged `arnaque` (notifications, OTP; n = 15) | 13.3 % |
| Category accuracy / macro-F1 on test scams (n = 190) | 80.5 % / 0.748 |
| Detection after each of 7 disguises (with normalization) | 98.9 % to 100 % |

7 of 8 pre-registered objectives are met. The missed one is the false-positive rate on
hard legitimate West-African notifications.

## Known limitations and failure modes

1. **Geography of the real data.** Real scams come from France, Belgium and Canada.
   West-African scams in the data are hand-written or reconstructed, so performance on
   real Ivorian traffic is not yet measured.
2. **Legitimate credits and refunds.** Learning from many real French "refund" scams,
   the model can flag legitimate West-African notifications such as "votre prêt a été
   remboursé" or "votre compte a été crédité" (2 of 15 test notifications; a salary
   credit is rated `suspect` in manual checks). Real West-African legitimate
   notifications are the fix.
3. **Scam type** is weaker than detection (80.5 %).
4. **Marketplace scams without a link** (a buyer moving the conversation to e-mail) are
   the one real scam family that was missed in the test split.
5. **Label noise** in user-reported data: estimated at 13 % before the human review; the
   review is one person's judgement and is published for audit.

## Ethical considerations

- **Privacy:** phone numbers, codes, references and e-mails are masked by the same code
  in the dataset and at inference; corpus tags (names, dates, identifiers) are rewritten
  to placeholders; the API never logs SMS text; the demo stores nothing.
- **Harm from errors:** a false `legitime` may reassure a victim; a false `arnaque` may
  make someone ignore a real notification. Hence three verdicts, advice that always points
  to official channels, and the out-of-scope list above.
- **Attribution:** IMC'25 and 88milSMS are used under CC BY 4.0 and cited in
  [`data/sources/README.md`](../data/sources/README.md).
- **Trademarks:** operator names are used descriptively; no logos; not affiliated.

## How to reproduce

```bash
python -m sikaguard_lab.import_imc25
python -m sikaguard_lab.import_88milsms --n-train 800 --n-eval 0 --exclude data/eval/88milsms_eval.csv
python -m sikaguard_lab.build --consumed data/history/test_0.1.0.dev0.csv --consumed data/history/test_0.1.0.dev1.csv
python -m sikaguard_lab.train && python -m sikaguard_lab.evaluate
```
