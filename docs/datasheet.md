# Datasheet — sikaguard SMS dataset `0.1.0.dev2`

Following *Datasheets for Datasets* (Gebru et al., 2021).

## Motivation

**Why was the dataset created?** Public SMS-spam datasets are almost all in English.
There is no open dataset of French-language scam SMS from West Africa, where Mobile
Money scams are common. This dataset is a first, documented step toward one.

**Who created it?** Ojewumi Asaph Felix, as an independent open-source project.

## Composition

**What does an instance represent?** One SMS, anonymized, with its labels.

| Version | Rows | Scams | Legitimate | Real SMS |
|---|---|---|---|---|
| `0.1.0.dev0` | 407 | 177 | 230 | none (seed only) |
| `0.1.0.dev1` | 602 | 217 | 385 | 150 real legitimate SMS |
| `0.1.0.dev2` | 2 063 | 1 028 | 1 035 | **811 real scams + 800 real legitimate SMS** |

Composition of `0.1.0.dev2` by origin: IMC'25 real scams 811, 88milSMS real personal SMS
800, hand-written seed 407, documented-campaign reconstructions and official notices 45.

Categories (test split in brackets): `phishing_lien` 397 (77), `autre_arnaque` 283 (54),
`usurpation_operateur` 240 (45), `investissement_emploi` 43 (5), `faux_transfert` 35 (5),
`faux_gain` 30 (4); `personnel` 875 (170), `notification_transaction` 70 (9),
`promo_operateur` 50 (7), `otp` 40 (6).

Countries: FR 1 059, CI 278, SN 68, BJ 24, BF 23, CM 18, BE 16, CA 16, ML 13, TG 11,
unknown 537 (IMC'25 reports often lack the country).

An **external benchmark** of 1 000 further real 88milSMS messages
(`data/eval/88milsms_eval.csv`) is never used for training.

**Fields:** `id`, `text`, `label`, `category`, `operateur_cible`, `pays`,
`source_type`, `date_observee`, `derive_de_modele`, `confiance_annotation`,
`campagne` (documented campaign id), `source_ref` (public URL of an official or press
source, never of a social-media post), `group_id`, `split`. Definitions: [annotation guide](annotation_guide.md).

**Is there a recommended split?** Yes, the `split` column: 1 681 train / 382 test, made
by group and stratified by category. A group joins near-duplicates (character 5-gram
Jaccard ≥ 0.8, transitive closure) and all rows of a documented campaign, so variants
of one scam or campaign never appear on both sides. The rows of the consumed
`0.1.0.dev0` and `0.1.0.dev1` test splits ([`data/history/`](../data/history/)) are forced
into train.

**Does it contain personal or sensitive data?** It should not. Phone numbers, names,
transaction references, codes and e-mails are replaced by `<TEL>`, `<NOM>`, `<REF>`,
`<CODE>`, `<EMAIL>`; links are defanged (`hxxp`, `[.]`). The build refuses any file
containing an unmasked phone number, an e-mail or a live link. Seed rows are fictional;
88milSMS was anonymised by its authors (names and numbers replaced, mapped to `<NOM>`
and `<TEL>`; messages with other personal tags were excluded).

**Is it self-contained?** Yes.

## Collection process

**Seed version.** Every SMS was written by the author from publicly documented scam
patterns (operator and authority warnings, press coverage, common knowledge of the
schemes) and from the usual format of operator notifications. Texts are not copies of
specific messages. Hard negatives were written on purpose (see the model card).

**88milSMS (dev1).** Random sample (seed 2011) of the CC BY 4.0 corpus by Panckhurst
et al. (2014), filtered (no links, no chain letters, 15–600 characters), imported with
`python -m sikaguard_lab.import_88milsms`. Bias: France, 2011, mostly students; capped
at 40 % of the legitimate class.

**Documented campaigns (dev1).** For 12 real, dated campaigns described by the PLCC,
the police, Orange Côte d'Ivoire or the press, 3–4 SMS were reconstructed to match the
published description (the sources do not reproduce the SMS verbatim), plus 5
legitimate official notices. Each row cites its source; facts were extracted, no
article text is reproduced.

**IMC'25 (dev2).** French subset (1 163 rows, 890 unique texts) of the labeled
smishing dataset of Agarwal et al. (ACM IMC 2025, CC BY 4.0), made of SMS that victims
reported publicly. Every unique text was read by the author; 119 were excluded (53
legitimate, 26 ambiguous, 18 advertising or political, 9 replies of the French 33700
service, 8 fragments, 5 not in French) and 1 was re-typed by hand. The corpus' Presidio
tags were rewritten so that no tag exists in one class only (names → `<NOM>`, numbers →
`<TEL>`/`<REF>`, dates → plain dates, links → shortener domain or `<URL>`). Imported with
`python -m sikaguard_lab.import_imc25`.

**Real West-African scams (planned).** Collection from public sources only: operator and
authority alerts, press articles, and social-media posts where people report a scam,
following the inclusion rules of the [annotation guide](annotation_guide.md).
Detailed provenance of social-media posts stays in a private folder (`data/raw/`,
never published) to protect the people who report scams.

## Preprocessing

Validation against the schema, exact de-duplication after normalization, near-duplicate
grouping, grouped stratified split (`python -m sikaguard_lab.build`). Raw text is kept
(case, accents, spelling, emojis); normalization happens in the model.

## Labeling quality

Single annotator (the author) for the seed. For real-data versions, 10 % of each batch
is re-annotated after one week and Cohen's kappa is published here. *Not yet measured.*

## Uses

**Intended:** training and evaluating scam detectors for French SMS; research on
low-resource and adversarial text classification; awareness material.
**Should not be used for:** identifying, profiling or accusing people or phone numbers;
claims about the real prevalence of scams (the seed data has no prevalence meaning).

## Distribution and maintenance

Distributed with the repository; a Hugging Face dataset release is planned for the
first real-data version. Versions follow semantic versioning; the test split of a
version is never modified. Anyone can request the removal of a row through a GitHub
issue. Maintainer: the author.

## License

Seed dataset: CC BY 4.0. Future subsets built from third-party corpora keep their own
licenses and are distributed separately.
