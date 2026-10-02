# Guide d'annotation — sikaguard

Ce guide fixe les règles pour collecter et étiqueter les SMS du jeu de données.
Il est la référence en cas de doute : **deux annotateurs qui suivent ce guide
doivent produire la même étiquette.**

## 1. Règle d'inclusion

Un SMS entre dans le jeu de données seulement si :

| Label | Condition |
|---|---|
| `arnaque` | L'arnaque est **confirmée** : alerte d'un opérateur, d'une autorité (ex. plateforme de lutte contre la cybercriminalité), article de presse, ou signalement explicite d'une victime (« je me suis fait arnaquer », « c'est une arnaque, attention »). |
| `legitime` | Le message provient d'une source fiable (modèle officiel d'opérateur, corpus de recherche publié) ou est un message personnel sans aucune demande suspecte. |

**Exclure :** les messages postés avec seulement « est-ce une arnaque ? » sans
réponse fiable, les captures illisibles, les doublons exacts.

## 2. Taxonomie

### Arnaques (`label = arnaque`)

| Catégorie | Définition | Indice décisif |
|---|---|---|
| `faux_transfert` | L'escroc prétend avoir envoyé de l'argent « par erreur » et demande de le renvoyer. | « par erreur », « renvoie », fausse notification de dépôt. |
| `usurpation_operateur` | L'escroc se fait passer pour un opérateur, une banque ou un service client pour obtenir un code, un PIN ou une action sur le compte. | Demande de code / PIN, menace de blocage, « service client ». |
| `faux_gain` | Gain, tombola, cadeau ou bonus inattendu, généralement contre des frais. | « Félicitations », « gagné », « frais de dossier / livraison ». |
| `phishing_lien` | Le cœur de l'arnaque est un **lien** vers une fausse page. | Lien vers un domaine suspect ou raccourci. |
| `investissement_emploi` | Argent facile, placement miracle, crypto, faux emploi, fausse bourse, faux prêt. | « doublez », « rendement garanti », « recrutement » + frais. |
| `autre_arnaque` | Tout le reste : faux proche en détresse, faux marabout, chantage, fausse amende, fausse location. | — |

**Priorité en cas de chevauchement** : `phishing_lien` si le lien est le moyen
principal ; sinon `usurpation_operateur` si l'escroc imite une institution ;
sinon la catégorie la plus spécifique.

### Messages légitimes (`label = legitime`)

| Catégorie | Définition |
|---|---|
| `notification_transaction` | Confirmation de transfert, dépôt, retrait, paiement, alerte bancaire. |
| `otp` | Code de vérification ou de connexion envoyé par un service. |
| `promo_operateur` | Offre commerciale, information de service, jeu-concours officiel. |
| `personnel` | Message entre particuliers. |

## 3. Autres colonnes

| Colonne | Valeurs | Règle |
|---|---|---|
| `operateur_cible` | `orange`, `mtn`, `moov`, `wave`, `banque`, `autre`, `aucun` | Opérateur ou institution mentionné ou imité. |
| `pays` | `CI`, `SN`, `BF`, `ML`, `BJ`, `TG`, `CM`, `NE`, `GN`, `FR`, `BE`, `CA`, `XX` | Pays de la source ; `XX` si inconnu. |
| `source_type` | `operateur`, `autorite`, `presse`, `reseau_social`, `corpus_recherche`, `depot_open_source`, `amorcage` | Type de la source (voir §5). `depot_open_source` : message réel publié dans le code d'un projet open source (tests d'un analyseur de SMS, par exemple). |
| `date_observee` | `AAAA-MM` ou vide | Mois de publication de la source. |
| `derive_de_modele` | `true` / `false` | `true` si le texte a été reconstitué d'après un modèle et n'est pas une copie d'un SMS réel. |
| `confiance_annotation` | `haute` / `moyenne` | `moyenne` si l'étiquette a demandé une interprétation. |

## 4. Anonymisation (obligatoire)

Avant d'enregistrer un SMS :

1. Remplacer **tous** les numéros de téléphone par `<TEL>` (y compris celui de l'escroc : c'est souvent une puce volée).
2. Remplacer les noms de personnes par `<NOM>`.
3. Remplacer les identifiants de transaction par `<REF>` et les codes secrets / OTP par `<CODE>`.
4. Remplacer les adresses e-mail par `<EMAIL>`.
5. **Désamorcer les liens** : `http` → `hxxp`, `.` → `[.]` (ex. `hxxps://faux-site[.]xyz`).
6. **Conserver** : montants, noms d'opérateurs, fautes d'orthographe, émojis, majuscules.

Aide : `from sikaguard.pii import anonymize` applique les points 1, 3, 4 et 5
automatiquement. Les noms (point 2) restent manuels. `python -m sikaguard_lab.build`
refuse tout fichier contenant un numéro, un e-mail ou un lien non désamorcé.

## 5. Provenance

- La provenance détaillée des publications de réseaux sociaux (URL, capture)
  est conservée **uniquement** dans `data/raw/`, qui n'est jamais publié.
- Les sources officielles et les articles de presse peuvent être cités dans la
  datasheet.

## 6. Contrôle qualité

- Une semaine après l'annotation d'un lot, ré-annoter un échantillon aléatoire
  de 10 % sans regarder les premières étiquettes, puis calculer le kappa de
  Cohen. Le résultat est publié dans `docs/datasheet.md`.
- Toute catégorie de moins de 15 exemples au moment du gel est fusionnée dans
  `autre_arnaque`.

## 7. Exemples limites

| SMS | Étiquette | Pourquoi |
|---|---|---|
| « Orange Money ne vous demandera jamais votre code secret. » | `legitime / notification_transaction` ou `promo_operateur` | Mise en garde, pas une demande. |
| « Stp envoie-moi 2000 pour le taxi, je te rembourse demain » | `legitime / personnel` | Demande d'argent entre proches, sans signal d'usurpation. |
| « Maman c'est moi, j'écris avec le numéro d'un ami, envoie vite 20 000 » | `arnaque / autre_arnaque` | Changement de numéro + urgence + argent : schéma du faux proche. |
| « Jeu MTN : envoyez JEU au 7575 et tentez de gagner… Règlement sur … » | `legitime / promo_operateur` | Jeu officiel avec règlement, aucun frais pour « débloquer » un gain. |
| « Votre compte est bloqué après 3 saisies erronées du code. Rendez-vous en agence. » | `legitime / notification_transaction` | Renvoie vers l'agence, ne demande rien. |
