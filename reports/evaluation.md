# sikaguard — evaluation report

> **Seed data warning.** This model was trained and tested on the *seed dataset*:
> SMS written by hand from publicly documented scam patterns, not real collected
> messages. These numbers validate the pipeline; they are **not** an estimate of
> real-world performance. Real-data results will replace them in v0.1.0.

Model `0.1.0.dev2` · dataset `0.1.0.dev2` · 1681 train / 382 test SMS · split by near-duplicate group, stratified by category · test split opened once.

## Benchmark

Average precision (area under the precision-recall curve) with 95 % bootstrap CI.

| Model | CV AP (train) | Test AP [95 % CI] | Test F1 | Recall @ precision 95 % |
|---|---|---|---|---|
| B0 majority class | 0.498 | 0.497 [0.448, 0.550] | 0.000 | 0.0 % |
| B1 rules only | 0.676 | 0.676 [0.622, 0.725] | 0.547 | 10.0 % |
| B2 naive Bayes (words) | 0.985 | 0.992 [0.985, 0.997] | 0.939 | 96.8 % |
| B3 linear SVM | 0.997 | 1.000 [1.000, 1.000] | 0.990 | 100.0 % |
| B4 sikaguard (retained) | 0.995 | 0.999 [0.998, 1.000] | 0.990 | 100.0 % |

Regularization chosen by grouped CV: C = 4.0 (strongest regularization within 0.001 AP of the best).

## Operating point (three verdicts)

Thresholds chosen on out-of-fold train predictions: `arnaque` if score ≥ 0.317 (precision ≥ 95 %), `legitime` if score < 0.305 (recall ≥ 99 %), `suspect` in between.

| True label \ verdict | arnaque | suspect | legitime |
|---|---|---|---|
| arnaque | 189 | 0 | 1 |
| legitime | 4 | 1 | 187 |

- Precision of the `arnaque` verdict: 97.9 %
- Scams flagged `arnaque`: 99.5 %; flagged `arnaque` or `suspect`: 99.5 %
- Legitimate SMS flagged `arnaque`: 2.1 %; `arnaque` or `suspect`: 2.6 %
- **Hard legitimate SMS** (transaction notifications and OTP codes, n = 15): false-positive rate 13.3 %, flagged suspect or worse 13.3 %
- Category model on test scams (n = 190): accuracy 80.5 %, macro-F1 0.748

![Precision-recall curve](pr_curve.png)

## Per category (test)

| Category | Label | n | Detected / flagged |
|---|---|---|---|
| autre_arnaque | arnaque | 54 | 98.2 % |
| faux_gain | arnaque | 4 | 100.0 % |
| faux_transfert | arnaque | 5 | 100.0 % |
| investissement_emploi | arnaque | 5 | 100.0 % |
| notification_transaction | legitime | 9 | 22.2 % |
| otp | legitime | 6 | 0.0 % |
| personnel | legitime | 170 | 1.2 % |
| phishing_lien | arnaque | 77 | 100.0 % |
| promo_operateur | legitime | 7 | 14.3 % |
| usurpation_operateur | arnaque | 45 | 100.0 % |

## Adversarial robustness

Share of test scams still flagged (`arnaque` or `suspect`) after each disguise. *Without normalization* is the same model trained on raw lower-cased text.

| Disguise | With normalization | Without normalization |
|---|---|---|
| original | 99.5 % | 99.5 % |
| leetspeak | 99.0 % | 96.3 % |
| homoglyphs | 99.5 % | 94.7 % |
| spaced_letters | 99.5 % | 98.4 % |
| zero_width | 99.5 % | 99.5 % |
| emojis | 99.5 % | 99.0 % |
| strip_accents | 99.5 % | 99.5 % |
| upper | 100.0 % | 100.0 % |

## Per source (test)

| Source | n | AP | Scams flagged | Legit flagged `arnaque` |
|---|---|---|---|---|
| 88milSMS (real legitimate SMS) | 163 | — | — | 0.6 % |
| IMC'25 (real scam SMS) | 161 | — | 99.4 % | — |
| documented campaigns (CI/SN) | 3 | — | 100.0 % | — |
| seed (hand-written) | 55 | 0.997 | 100.0 % | 10.3 % |

## Real SMS only (test split)

Real scam SMS reported by victims (IMC'25, n = 161) against real legitimate SMS (88milSMS, n = 163), all never seen in training.

- Average precision: **1.000** [0.999, 1.000]
- Recall at 95 % precision: 100.0 % [100.0 %, 100.0 %]
- Real scams flagged `arnaque` or `suspect`: **99.4 %** [98.1 %, 100.0 %]
- Real scams flagged `arnaque`: 99.4 % [98.1 %, 100.0 %]
- Real legitimate SMS flagged `arnaque`: 0.6 %

Real scams judged legitimate (first 15):

- Bjr,vtre Electro est tjr dispo?si oui me répondre a mn adresse mail:<EMAIL>

## Real SMS benchmark (never used for training)

1000 authentic French SMS from the 88milSMS corpus (CC BY 4.0), disjoint from the training sample. Every one is legitimate, so every alert is a false alarm.

- Flagged `arnaque`: **0.9 %** [95 % CI 0.4 %, 1.6 %]
- Flagged `arnaque` or `suspect`: 0.9 % [95 % CI 0.4 %, 1.6 %]

False alarms (first 10):

- Pr cet hiver a noel je nous ai payé des entrees pr disneyland paris (les deux parcs) et ca fait bcp dargent en tt ^^ surtout que bientot je vais devoir faire un cheque de 500 euros pr les modeles bref heureusement que g des sous de coté ^^ et je tai dit que je te demanderai pas de tt me rembourser parce que cest pas la peine ca me fait plaisir de toffrir des trucs oci ^^
- L'art de persuader (communication) est 1/4 de la richesse au us
- Parce que j'en peux plus de cette double-hypocrisie qu'on joue, et qu'il faudra qu'on ait notre toute dernière discussion. Et la nuit et l'alcool aidant, j'espère bien qu'on se dira tout ce qu'on a sur le coeur : une sorte de discussion "purifiante" pour repartir plus légèrement et honnetement ensuite.
- Avant 17h hein... humhum...
- Désolé, je fais des courses aux 3F. =/
- Le 11 vous etes invités il y à <NOM> qui sera là
- <NOM> est super content, son article sur les lois de programmation va etre pubié à la rdp de janvier, et sa note à la gazette du palais. Son dossier pr le cnu est complet
- Coucou miss! Jpense rester chez moi cet aprem malheureusement, le temps passe trop vite et Jessaye de travailler..
- Apele si c pour une couleur il te prendron + vite . Le bon es valable juska fevrier 2012

## Pre-registered objectives

| Objective | Target | Achieved | Met |
|---|---|---|---|
| test_average_precision | ≥ 0.95 | 0.9993 | yes |
| recall_at_precision_95 | ≥ 0.9 | 1.0 | yes |
| hard_legit_false_positive_rate | ≤ 0.05 | 0.1333 | no |
| min_detection_under_perturbation | ≥ 0.85 | 0.9895 | yes |
| real_sms_false_positive_rate | ≤ 0.05 | 0.009 | yes |
| real_test_average_precision | ≥ 0.95 | 0.9998 | yes |
| real_scam_detection_rate | ≥ 0.9 | 0.9938 | yes |
| real_scam_arnaque_rate | ≥ 0.85 | 0.9938 | yes |

## Notes

- v0.1.0.dev2 protocol: the dev0 and dev1 test splits were consumed (155 rows forced into train); this test split is new and was opened once.
- Real data: 811 real French scam SMS reported by victims (IMC'25, CC BY 4.0, France/Belgium/Canada context), human-reviewed (119 of 890 unique texts removed as legitimate, ambiguous, advertising, non-French or fragments), and 800 + 1 000 real legitimate SMS (88milSMS). Real scams were grouped by near-duplicate template, so test templates were never seen in training.
- Limit: no real collected scam SMS from West Africa yet; West-African scams are seed texts and reconstructions of documented campaigns. The model stays flagged not_for_production until real West-African scams are added.

## All test errors (6)

| Label | Category | Verdict | Score | SMS |
|---|---|---|---|---|
| legitime | notification_transaction | arnaque | 0.63 | Votre prêt de 25 000 FCFA a été remboursé intégralement. Merci pour votre confiance. |
| legitime | notification_transaction | arnaque | 0.70 | Votre compte épargne a été crédité des intérêts trimestriels: 4 250 XOF. |
| legitime | promo_operateur | suspect | 0.31 | Wave: pour votre sécurité, activez le verrouillage de l'application dans les paramètres. |
| legitime | personnel | arnaque | 0.46 | URGENT: la réunion est avancée à 14h, préviens les autres |
| legitime | personnel | arnaque | 0.42 | Bonjour, <NOM> du site Récupe. Puis-je passer récupérer les ampoules demain à 19h? Merci de me donner votre adresse. Cordialement |
| arnaque | autre_arnaque | legitime | 0.20 | Bjr,vtre Electro est tjr dispo?si oui me répondre a mn adresse mail:<EMAIL> |

## Reproduce

```bash
python -m sikaguard_lab.build
python -m sikaguard_lab.train
python -m sikaguard_lab.evaluate
```
