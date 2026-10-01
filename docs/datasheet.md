# Datasheet — sikaguard SMS dataset `0.1.0.dev0`

Following *Datasheets for Datasets* (Gebru et al., 2021).

## Motivation

**Why was the dataset created?** Public SMS-spam datasets are almost all in English.
There is no open dataset of French-language scam SMS from West Africa, where Mobile
Money scams are common. This dataset is a first, documented step toward one.

**Who created it?** Ojewumi Asaph Felix, as an independent open-source project.

## Composition

**What does an instance represent?** One SMS, anonymized, with its labels.

| Version | Rows | Scams | Legitimate | Real collected SMS |
|---|---|---|---|---|
| `0.1.0.dev0` (seed) | 407 | 177 | 230 | **0** — every row is `source_type=amorcage` |

Scam categories (test split in brackets): `usurpation_operateur` 32 (7),
`faux_transfert` 30 (6), `faux_gain` 30 (6), `phishing_lien` 30 (6),
`investissement_emploi` 30 (6), `autre_arnaque` 25 (5).
Legitimate categories: `personnel` 75 (15), `notification_transaction` 70 (14),
`promo_operateur` 45 (9), `otp` 40 (8).

Countries: CI 236, SN 65, BJ 24, BF 23, CM 18, ML 13, TG 11, unknown 17.

**Fields:** `id`, `text`, `label`, `category`, `operateur_cible`, `pays`,
`source_type`, `date_observee`, `derive_de_modele`, `confiance_annotation`,
`group_id`, `split`. Definitions: [annotation guide](annotation_guide.md).

**Is there a recommended split?** Yes, the `split` column: 325 train / 82 test, made
by near-duplicate group (character 5-gram Jaccard ≥ 0.8, transitive closure) and
stratified by category, so variants of one scam never appear on both sides.

**Does it contain personal or sensitive data?** It should not. Phone numbers, names,
transaction references, codes and e-mails are replaced by `<TEL>`, `<NOM>`, `<REF>`,
`<CODE>`, `<EMAIL>`; links are defanged (`hxxp`, `[.]`). The build refuses any file
containing an unmasked phone number, an e-mail or a live link. Seed rows are fictional.

**Is it self-contained?** Yes.

## Collection process

**Seed version.** Every SMS was written by the author from publicly documented scam
patterns (operator and authority warnings, press coverage, common knowledge of the
schemes) and from the usual format of operator notifications. Texts are not copies of
specific messages. Hard negatives were written on purpose (see the model card).

**Real-data versions (planned).** Collection from public sources only: operator and
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
