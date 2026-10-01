# sikaguard — evaluation report

> **Seed data warning.** This model was trained and tested on the *seed dataset*:
> SMS written by hand from publicly documented scam patterns, not real collected
> messages. These numbers validate the pipeline; they are **not** an estimate of
> real-world performance. Real-data results will replace them in v0.1.0.

Model `0.1.0.dev1` · dataset `0.1.0.dev1` · 498 train / 104 test SMS · split by near-duplicate group, stratified by category · test split opened once.

## Benchmark

Average precision (area under the precision-recall curve) with 95 % bootstrap CI.

| Model | CV AP (train) | Test AP [95 % CI] | Test F1 | Recall @ precision 95 % |
|---|---|---|---|---|
| B0 majority class | 0.357 | 0.346 [0.250, 0.442] | 0.000 | 0.0 % |
| B1 rules only | 0.891 | 0.959 [0.901, 1.000] | 0.959 | 55.6 % |
| B2 naive Bayes (words) | 0.976 | 0.996 [0.986, 1.000] | 0.935 | 94.4 % |
| B3 linear SVM | 0.987 | 0.997 [0.988, 1.000] | 0.972 | 97.2 % |
| B4 sikaguard (retained) | 0.985 | 0.997 [0.988, 1.000] | 0.972 | 97.2 % |

Regularization chosen by grouped CV: C = 30.0 (strongest regularization within 0.001 AP of the best).

## Operating point (three verdicts)

Thresholds chosen on out-of-fold train predictions: `arnaque` if score ≥ 0.493 (precision ≥ 95 %), `legitime` if score < 0.108 (recall ≥ 98 %), `suspect` in between.

| True label \ verdict | arnaque | suspect | legitime |
|---|---|---|---|
| arnaque | 35 | 1 | 0 |
| legitime | 1 | 2 | 65 |

- Precision of the `arnaque` verdict: 97.2 %
- Scams flagged `arnaque`: 97.2 %; flagged `arnaque` or `suspect`: 100.0 %
- Legitimate SMS flagged `arnaque`: 1.5 %; `arnaque` or `suspect`: 4.4 %
- **Hard legitimate SMS** (transaction notifications and OTP codes, n = 17): false-positive rate 0.0 %, flagged suspect or worse 5.9 %
- Category model on test scams (n = 36): accuracy 75.0 %, macro-F1 0.738

![Precision-recall curve](pr_curve.png)

## Per category (test)

| Category | Label | n | Detected / flagged |
|---|---|---|---|
| autre_arnaque | arnaque | 6 | 100.0 % |
| faux_gain | arnaque | 4 | 100.0 % |
| faux_transfert | arnaque | 5 | 100.0 % |
| investissement_emploi | arnaque | 8 | 100.0 % |
| notification_transaction | legitime | 11 | 9.1 % |
| otp | legitime | 6 | 0.0 % |
| personnel | legitime | 42 | 0.0 % |
| phishing_lien | arnaque | 7 | 100.0 % |
| promo_operateur | legitime | 9 | 22.2 % |
| usurpation_operateur | arnaque | 6 | 100.0 % |

## Adversarial robustness

Share of test scams still flagged (`arnaque` or `suspect`) after each disguise. *Without normalization* is the same model trained on raw lower-cased text.

| Disguise | With normalization | Without normalization |
|---|---|---|
| original | 100.0 % | 100.0 % |
| leetspeak | 100.0 % | 97.2 % |
| homoglyphs | 100.0 % | 88.9 % |
| spaced_letters | 100.0 % | 100.0 % |
| zero_width | 100.0 % | 100.0 % |
| emojis | 100.0 % | 100.0 % |
| strip_accents | 100.0 % | 100.0 % |
| upper | 100.0 % | 100.0 % |

## Per source (test)

| Source | n | AP | Scams flagged | Legit flagged `arnaque` |
|---|---|---|---|---|
| amorcage | 63 | 0.996 | 100.0 % | 2.9 % |
| autorite | 7 | — | 100.0 % | — |
| corpus_recherche | 33 | — | — | 0.0 % |
| operateur | 1 | — | — | 0.0 % |

## Real SMS benchmark (never used for training)

1000 authentic French SMS from the 88milSMS corpus (CC BY 4.0), disjoint from the training sample. Every one is legitimate, so every alert is a false alarm.

- Flagged `arnaque`: **0.6 %** [95 % CI 0.2 %, 1.1 %]
- Flagged `arnaque` or `suspect`: 1.3 % [95 % CI 0.6 %, 2.0 %]

False alarms (first 10):

- Commercial pour k par k avec des pure conditions de salaire et tout
- Jalousie mal placée de londres, merci. T'avais prévu ça avec ton pote. Tu voulais pas y aller avec moi comme ça précisément. Puisque t'façons tu te bougeait pas. Maintenant ça ne m'empeche pas de le faire. J'y suis déjà allé, et J'y retournerai pas qu'une fois. Avec toi c'est différent. Et je pense le vouloir meme plus que toi. Donc NON j'ai pas dit à <NOM> déchire ton billet on va à berlin pour pas créer un conflit intergalactique
- Putain jte jure tu craques toi à me supprimer de facebook tout le temps, ce matin déja on était plus amis donc je t ai renvoyé une demande, t acceptes jvois que t es toujours célibataire alors que t as fais le ménage du reste, écoute me prend pas la tete je t ai pas supprimé une seule fois et quand jte dis de me dire à quelle heure tu viens chez moi tu pourrais prendre la peine de me répondre au moins par facebook tu crois pas?
- Pr cet hiver a noel je nous ai payé des entrees pr disneyland paris (les deux parcs) et ca fait bcp dargent en tt ^^ surtout que bientot je vais devoir faire un cheque de 500 euros pr les modeles bref heureusement que g des sous de coté ^^ et je tai dit que je te demanderai pas de tt me rembourser parce que cest pas la peine ca me fait plaisir de toffrir des trucs oci ^^
- Désolé, je fais des courses aux 3F. =/
- Oui c sur ms bon tu décide un peu de ton emploi du temps au début! Et puis tu peux "moduler" pr les k exceptionnels,^^(oui dsl g pas u le temps de répondre avant maintenant ^^')

## Pre-registered objectives

| Objective | Target | Achieved | Met |
|---|---|---|---|
| test_average_precision | ≥ 0.95 | 0.9971 | yes |
| recall_at_precision_95 | ≥ 0.9 | 0.9722 | yes |
| hard_legit_false_positive_rate | ≤ 0.05 | 0.0 | yes |
| min_detection_under_perturbation | ≥ 0.85 | 1.0 | yes |
| real_sms_false_positive_rate | ≤ 0.05 | 0.006 | yes |

## Notes

- v0.1.0.dev1 protocol: the 0.1.0.dev0 test split was consumed (its errors had been analysed); its 82 rows were forced into train and a new test split was drawn. Caveat: the author of the new rows (88milSMS sampling, campaign reconstructions, signal fixes) had seen the dev0 errors, so these numbers may be slightly optimistic; the real-SMS benchmark is the least biased measurement.
- Documented-campaign rows (source_type autorite / operateur / presse) are reconstructions of real, dated Côte d'Ivoire and Senegal campaigns; every row of a campaign sits on the same side of the split, so test campaigns were never seen in training.

## All test errors (4)

| Label | Category | Verdict | Score | SMS |
|---|---|---|---|---|
| arnaque | phishing_lien | suspect | 0.15 | Votre compte a été crédité de 20 000 F. Consultez le détail: s[.]id/credit-om |
| legitime | notification_transaction | suspect | 0.34 | Votre compte a été crédité de 350 000 XOF (VIREMENT SALAIRE SEPT). Solde: 412 000 XOF. |
| legitime | promo_operateur | suspect | 0.40 | Bonus: rechargez 2000F aujourd'hui et recevez 100% de bonus d'appel valable 3 jours. |
| legitime | promo_operateur | arnaque | 0.78 | Orange Money: envoyez de l'argent vers la Côte d'Ivoire à moitié prix jusqu'au 15 octobre. |

## Reproduce

```bash
python -m sikaguard_lab.build
python -m sikaguard_lab.train
python -m sikaguard_lab.evaluate
```
