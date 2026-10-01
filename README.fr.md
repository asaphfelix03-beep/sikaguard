# sikaguard 🛡️

**Détection explicable des arnaques par SMS et Mobile Money, en français d'Afrique de l'Ouest.**

*[Read in English](README.md)*

`sikaguard` (« sika » veut dire « argent » en akan et en éwé) dit si un SMS est une
arnaque, **de quel type**, et **pourquoi** : faux transfert « envoyé par erreur », faux
service client qui demande votre code, faux gain, lien piégé, faux investissement ou
faux emploi.

```python
>>> from sikaguard import analyze
>>> r = analyze("Cher client Orange Money, votre compte sera bloqué. Envoyez votre code secret au 0701020304")
>>> r.verdict, r.category
('arnaque', 'usurpation_operateur')
>>> for reason in r.reasons: print("-", reason.message)
- Le message demande un code secret (PIN, OTP, mot de passe). Aucun opérateur ni aucune banque ne le demande jamais.
- Le message menace de bloquer ou de suspendre votre compte ou votre numéro.
- Formulation proche d'arnaques connues : « client », « compte », « code secret ».
```

> **Statut : alpha.** Le modèle livré (`0.1.0.dev1`) est entraîné sur 602 SMS : un jeu
> d'amorçage rédigé à la main, de **vrais SMS légitimes** (corpus de recherche 88milSMS)
> et des reconstitutions de **12 campagnes d'arnaque réelles et datées** en Côte d'Ivoire
> et au Sénégal (PLCC, police, opérateurs, presse). Il n'a pas encore vu de vrais SMS
> d'arnaque collectés : il reste marqué *not for production*, et cette collecte est la
> prochaine étape ([feuille de route](ROADMAP.md)). Ne l'utilisez pas pour bloquer des
> messages automatiquement.

## Pourquoi

Le Mobile Money est la façon dont des millions de personnes en Afrique de l'Ouest
envoient et reçoivent de l'argent, et les arnaques par SMS le suivent. Or presque tous
les jeux de données publics de spam SMS sont en anglais : les filtres existants ne
couvrent pas le français tel qu'on l'écrit à Abidjan, Dakar ou Ouagadougou.

sikaguard apporte deux choses :

1. **Un jeu de données ouvert et documenté** de SMS d'arnaque en français d'Afrique de
   l'Ouest, avec une taxonomie, un guide d'annotation et une datasheet.
2. **Un détecteur léger, explicable et résistant aux techniques d'évasion**, que tout
   développeur peut intégrer (`pip`), appeler (API REST) ou essayer ([démo](demo/)).

## Fonctionnalités

- **Trois verdicts** : `arnaque` / `suspect` / `legitime`, avec des seuils réglables.
- **Type d'arnaque** : six catégories, chacune avec un conseil pratique.
- **Explications exactes** : 19 signaux d'alerte (« demande un code secret », « crée
  l'urgence », « lien suspect », « demande d'installer un APK », « dit avoir changé de
  numéro », « demande le secret »…) et mots qui ont le plus pesé.
- **Normalisation anti-évasion** : leetspeak (`0range M0ney`), lettres cyrilliques
  déguisées, lettres espacées (`c o d e`), caractères invisibles, émojis dans les mots,
  liens écrits avec des lettres déguisées.
- **Confidentialité par conception** : numéros, codes, références et e-mails masqués
  avant le modèle ; l'API ne journalise jamais le texte des SMS.
- **Chargement sécurisé du modèle** : `skops` (pas de `pickle`), empreinte SHA-256
  vérifiée, liste blanche de types.
- **Léger et rapide** : modèle d'environ 1 Mo, scikit-learn seulement, pas de GPU ;
  4,8 ms en médiane et 9 ms au 95e centile par SMS, 1,6 ms par SMS en lot.

## Installation et utilisation

```bash
pip install sikaguard            # bibliothèque + ligne de commande
pip install "sikaguard[api]"     # + API REST
sikaguard "Félicitations! Vous avez gagné 1 000 000 F. Payez 5000 F de frais pour recevoir."
uvicorn sikaguard.api:app --port 8000
```

En attendant la première publication sur PyPI :
`pip install git+https://github.com/asaphfelix03-beep/sikaguard`.

Détails de l'API, de Docker et de la démo : voir le [README anglais](README.md#use).

## Évaluation

Rapport complet : [`reports/evaluation.md`](reports/evaluation.md) (en anglais).

**La mesure la plus importante : 1 000 vrais SMS** (corpus 88milSMS), jamais vus à
l'entraînement. Tous sont légitimes, donc chaque alerte est une fausse alarme :
**0,6 %** sont classés `arnaque` (IC 95 % : 0,2 – 1,1 %).

| Objectif fixé à l'avance | Cible | 0.1.0.dev0 | **0.1.0.dev1** |
|---|---|---|---|
| Précision moyenne (PR-AUC) | ≥ 0,95 | 0,973 ✅ | **0,997** ✅ |
| Rappel à 95 % de précision | ≥ 90 % | 80,6 % ❌ | **97,2 %** ✅ |
| Faux positifs sur SMS légitimes difficiles | ≤ 5 % | 13,6 % ❌ | **0 %** ✅ |
| Détection sous le pire déguisement | ≥ 85 % | 91,7 % ✅ | **100 %** ✅ |
| Fausses alertes sur 1 000 vrais SMS *(ajouté en dev1)* | ≤ 5 % | — | **0,6 %** ✅ |

**Protocole** : découpage par groupe (quasi-doublons et campagnes : une campagne de test
n'est jamais vue à l'entraînement), validation croisée groupée sur l'entraînement
seulement, jeu de test ouvert une seule fois. Le test de la v0.1.0.dev0, dont les erreurs
avaient été analysées, a été **consommé** : archivé et forcé en entraînement.

**Lecture honnête** : le jeu de test est presque saturé, car ses arnaques sont rédigées
ou reconstituées, et de vraies arnaques seront plus difficiles. Le type d'arnaque reste le
point faible (75 % de bonne catégorie). Le banc d'essai sur vrais SMS est la mesure la
moins biaisée.

## Contribuer

La contribution la plus précieuse, ce sont les **données** : si vous avez reçu un SMS
d'arnaque, [signalez-le](https://github.com/asaphfelix03-beep/sikaguard/issues/new?template=nouvelle-arnaque.yml)
en retirant numéros et noms. Voir [CONTRIBUTING.md](CONTRIBUTING.md) et le
[guide d'annotation](docs/annotation_guide.md).

## Licence et avertissement

Code sous [licence MIT](LICENSE). sikaguard est un projet indépendant, **non affilié** à
Orange, MTN, Moov, Wave ni à aucune banque : leurs noms servent uniquement à décrire les
arnaques qui les imitent. L'outil aide à décider ; il ne remplace pas les canaux
officiels de votre opérateur ou de votre banque.
