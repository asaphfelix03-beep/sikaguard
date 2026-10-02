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
- Formulation proche d'arnaques connues : « client », « compte », « sera bloque ».
```

> **Statut : alpha.** Le modèle livré (`0.1.0.dev2`) est entraîné sur 2 063 SMS, dont
> **1 611 réels** : 811 vrais SMS d'arnaque signalés par des victimes (jeu de recherche
> IMC'25, relu à la main) et 800 vrais SMS personnels (corpus 88milSMS), plus un jeu
> d'amorçage ouest-africain et des reconstitutions de 12 campagnes documentées en Côte
> d'Ivoire et au Sénégal. Sur de vrais SMS jamais vus, il détecte **99,4 %** des arnaques
> avec **0,9 %** de fausses alertes. Les vraies arnaques viennent de France, de Belgique et
> du Canada : tant que de vrais SMS d'arnaque ouest-africains n'ont pas été collectés, le
> modèle reste marqué *not for production* ([feuille de route](ROADMAP.md)).

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
- **Léger et rapide** : modèle d'environ 2 Mo, scikit-learn seulement, pas de GPU ;
  1,8 ms en médiane et 3,1 ms au 95e centile par SMS, 0,6 ms par SMS en lot.

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

**Sur de vrais SMS jamais vus à l'entraînement :**

| | Résultat [IC 95 %] |
|---|---|
| **Vraies arnaques détectées** (161 signalements de victimes, IMC'25) | **99,4 %** [98,1 – 100 %] |
| **Fausses alertes sur 1 000 vrais SMS personnels** (banc 88milSMS) | **0,9 %** [0,4 – 1,6 %] |
| Précision moyenne, vraies arnaques contre vrais SMS personnels | 0,9998 |

| Objectif fixé à l'avance | Cible | dev0 | dev1 | **dev2** |
|---|---|---|---|---|
| Précision moyenne (test) | ≥ 0,95 | 0,973 ✅ | 0,997 ✅ | **0,999** ✅ |
| Rappel à 95 % de précision | ≥ 90 % | 80,6 % ❌ | 97,2 % ✅ | **100 %** ✅ |
| Faux positifs sur notifications et codes légitimes | ≤ 5 % | 13,6 % ❌ | 0 % ✅ | **13,3 %** ❌ |
| Détection sous le pire déguisement | ≥ 85 % | 91,7 % ✅ | 100 % ✅ | **98,9 %** ✅ |
| Fausses alertes sur 1 000 vrais SMS | ≤ 5 % | — | 0,6 % ✅ | **0,9 %** ✅ |
| Vraies arnaques signalées | ≥ 90 % | — | — | **99,4 %** ✅ |

**Protocole** : découpage par groupe (les variantes d'un même modèle d'arnaque et d'une même
campagne restent du même côté), validation croisée groupée sur l'entraînement seulement,
jeu de test ouvert une seule fois ; les tests des versions précédentes ont été consommés.

**Lecture honnête** : les vraies arnaques sont françaises, belges et canadiennes ; les
arnaques ouest-africaines du jeu restent rédigées ou reconstituées. L'objectif manqué en
découle : nourri de vraies arnaques françaises au « remboursement », le modèle signale 2
vraies notifications ouest-africaines sur 15. Le remède, ce sont de vraies notifications
ouest-africaines, pas un réglage sur le jeu de test.

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
