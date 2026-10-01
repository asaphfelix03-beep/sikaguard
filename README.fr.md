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
- Formulation proche d'arnaques connues : « secret au », « code secret », « cher client ».
```

> **Statut : alpha.** Le modèle livré (`0.1.0.dev0`) est entraîné sur un **jeu
> d'amorçage** : des SMS rédigés à la main d'après des schémas d'arnaque publiquement
> documentés, pas des SMS réels collectés. Tout le système fonctionne de bout en bout
> (données, entraînement, évaluation, bibliothèque, API, démo) ; la collecte réelle est
> la prochaine étape ([feuille de route](ROADMAP.md)). Ne l'utilisez pas pour bloquer
> des messages automatiquement.

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
- **Explications exactes** : signaux d'alerte (« demande un code secret », « crée
  l'urgence », « lien suspect ») et mots qui ont le plus pesé.
- **Normalisation anti-évasion** : leetspeak (`0range M0ney`), lettres cyrilliques
  déguisées, lettres espacées (`c o d e`), caractères invisibles, émojis dans les mots,
  liens écrits avec des lettres déguisées.
- **Confidentialité par conception** : numéros, codes, références et e-mails masqués
  avant le modèle ; l'API ne journalise jamais le texte des SMS.
- **Chargement sécurisé du modèle** : `skops` (pas de `pickle`), empreinte SHA-256
  vérifiée, liste blanche de types.
- **Léger** : modèle de 0,7 Mo, scikit-learn seulement, pas de GPU.

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

## Évaluation (données d'amorçage)

Sur 407 SMS, avec un découpage par groupe de quasi-doublons, une validation croisée
groupée et un jeu de test ouvert une seule fois :

| Objectif fixé à l'avance | Cible | Résultat | |
|---|---|---|---|
| Précision moyenne (PR-AUC) | ≥ 0,95 | 0,973 | ✅ |
| Rappel à 95 % de précision | ≥ 90 % | 80,6 % | ❌ |
| Faux positifs sur SMS légitimes difficiles | ≤ 5 % | 13,6 % | ❌ |
| Détection sous le pire déguisement | ≥ 85 % | 91,7 % | ✅ |

Ces chiffres valident le système ; ils **ne mesurent pas** la performance réelle,
puisque les données sont rédigées à la main. Les objectifs manqués sont analysés dans
le [rapport complet](reports/evaluation.md) et la [feuille de route](ROADMAP.md) : ils
n'ont **pas** été « corrigés » en regardant le jeu de test, ce qui rendrait les chiffres
sans valeur.

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
