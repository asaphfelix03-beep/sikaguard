# sikaguard — Spécification de design

- **Date :** 2026-09-30
- **Auteur :** Ojewumi Asaph Felix (asaphfelix03-beep)
- **Statut :** approuvé (conversation de brainstorming du 2026-09-30)

## 1. Intention

| | |
|---|---|
| **Ce que l'utilisateur a demandé** | Un projet Data + Sécurité, open source, réellement utile à d'autres, v1 en 1–2 semaines, « comme un grand expert ». |
| **Utilisateur principal** | Développeurs (fintechs, apps, bots) qui intègrent la détection via `pip` ou une API. |
| **Contribution originale** | Le premier jeu de données ouvert de SMS d'arnaque en français d'Afrique de l'Ouest (Mobile Money), plus un détecteur explicable et robuste aux techniques d'évasion. |
| **Succès** | `pip install sikaguard` → `analyze(texte)` renvoie verdict + type d'arnaque + raisons lisibles ; dataset, benchmark et model card publiés honnêtement. |

**En une phrase :** `sikaguard` (« sika » = argent en akan/éwé) détecte si un SMS est une arnaque, **de quel type**, et **pourquoi**.

### Hors périmètre v1 (→ `ROADMAP.md`)
Deep learning (CamemBERT), bot WhatsApp, langues locales (nouchi, dioula), application mobile, API publique hébergée.

## 2. Architecture

Quatre briques indépendantes :

| Brique | Rôle | Livrable |
|---|---|---|
| Pipeline de données | collecte → validation → anonymisation → dédoublonnage → découpage | dataset versionné + datasheet |
| Bibliothèque `sikaguard` | `analyze()` : normalisation, signaux, modèle, explication | paquet PyPI |
| API | FastAPI `POST /v1/analyze` | image Docker |
| Démo | Gradio (Hugging Face Space) | page publique |

Flux : sources → CSV brut (privé) → anonymisation → `data/processed/` → entraînement → `src/sikaguard/assets/model.skops` → bibliothèque → API / démo.

## 3. Données

### 3.1 Taxonomie
- **label** : `arnaque` | `legitime`
- **category** (arnaque) : `faux_transfert`, `usurpation_operateur`, `faux_gain`, `phishing_lien`, `investissement_emploi`, `autre_arnaque`
- **category** (legitime) : `notification_transaction`, `otp`, `promo_operateur`, `personnel`
- **operateur_cible** : `orange`, `mtn`, `moov`, `wave`, `banque`, `autre`, `aucun`
- **pays** : code ISO-2 (`CI`, `SN`, `BF`, `ML`, `BJ`, `TG`, `CM`, `FR`, `XX` inconnu)

### 3.2 Schéma d'une ligne
`id`, `text`, `label`, `category`, `operateur_cible`, `pays`, `source_type` (`operateur`, `autorite`, `presse`, `reseau_social`, `corpus_recherche`, `amorcage`), `date_observee` (AAAA-MM ou vide), `derive_de_modele` (bool), `group_id`, `split` (`train`|`test`), `confiance_annotation` (`haute`|`moyenne`).

Un validateur refuse : colonne manquante, valeur hors énumération, texte vide ou > 1 000 caractères, catégorie incohérente avec le label, numéro de téléphone non masqué.

### 3.3 Anonymisation
- Masquer : numéros → `<TEL>`, noms propres de personnes → `<NOM>` (annotation manuelle), identifiants de transaction → `<REF>`, codes numériques 4–8 chiffres hors montants → `<CODE>`.
- Conserver : montants, noms d'opérateurs, fautes, domaines des liens.
- Liens publiés « désamorcés » (`hxxp`, `[.]`).
- **La même normalisation est appliquée à l'inférence** (pas de train/serve skew).
- Provenance détaillée des réseaux sociaux : fichier privé `data/raw/` (ignoré par git).

### 3.4 Biais de source
Le corpus 88milSMS (France, 2011) risque d'apprendre le dialecte au lieu de l'arnaque. Parades : ≤ 40 % des légitimes, test « légitimes difficiles » (notifications Mobile Money réelles), métriques par source.

### 3.5 Dédoublonnage et découpage anti-fuite
1. Doublons exacts supprimés après normalisation.
2. Quasi-doublons : shingles de 5 caractères, Jaccard ≥ 0,8 → même `group_id` (union-find).
3. Découpage 80/20 **par groupe, stratifié** sur le label, graine fixe. Test gelé.

### 3.6 Annotation
Guide écrit (`docs/annotation_guide.md`). Une arnaque n'entre que si elle est confirmée (source officielle ou signalement explicite). Ré-annotation de 10 % à une semaine d'intervalle → kappa de Cohen publié.

### 3.7 Jeu d'amorçage (amendement du 2026-09-30)
Pour livrer un système **fonctionnel de bout en bout avant la fin de la collecte réelle**, le dépôt inclut `data/seed/seed_sms.csv` : des SMS **rédigés par l'auteur du code** d'après les schémas d'arnaque publiquement documentés et le format des notifications opérateurs, tous marqués `source_type=amorcage`, `derive_de_modele=true`.
- Le modèle entraîné sur ce jeu est versionné `0.1.0.dev0` et **n'est pas destiné à la production**.
- Les métriques qu'il produit valident le pipeline, **pas** la performance réelle ; le rapport et la model card le disent explicitement.
- La collecte réelle (sources publiques + 88milSMS après vérification de licence) remplace ce jeu pour `v0.1.0`.

### 3.8 Licences
Code : MIT. Dataset : CC BY 4.0 pour la partie originale ; si la licence de 88milSMS est non commerciale, sous-ensemble séparé sous sa licence propre.

## 4. Modèle

### 4.1 Normalisation (`normalize.py`)
Unicode NFKC → homoglyphes (cyrillique/grec → latin) → minuscules → suppression des accents → leetspeak intra-mot (`0→o`, `1→i`, `3→e`, `4→a`, `5→s`, `@→a`, `$→s`) sans toucher aux nombres purs → lettres espacées recollées (`c o d e` → `code`) → répétitions ≥ 3 réduites à 2 → masquage `<URL>`, `<TEL>`, `<CODE>` → espaces normalisés.
Les liens sont analysés **avant** masquage pour produire des indicateurs (raccourcisseur, IP, domaine sosie d'une marque).

### 4.2 Signaux experts (`signals.py`)
Chaque signal : `code`, fonction de détection sur texte normalisé, message FR. Liste v1 :
`demande_code_secret`, `demande_renvoi_argent`, `urgence`, `menace_blocage`, `gain_inattendu`, `frais_a_payer`, `lien_present`, `lien_raccourci`, `lien_suspect` (IP ou domaine sosie), `mention_operateur`, `contact_numero`, `promesse_gain_financier`, `offre_emploi`, `majuscules_excessives`, `montant_present`.

### 4.3 Modèle à deux étages (`model.py`)
- **Étage 1** (binaire) : `FeatureUnion` [TF-IDF caractères `char_wb` 2–5, TF-IDF mots 1–2, vecteur des signaux] → `LogisticRegression(class_weight="balanced")`.
- **Étage 2** (catégorie) : même extraction → régression logistique multinomiale, entraînée sur les arnaques uniquement ; appelée si verdict ≠ `legitime`.
- **Verdict à trois niveaux** : `arnaque` si score ≥ `seuil_haut`, `legitime` si score < `seuil_bas`, sinon `suspect`. Seuils choisis par validation croisée sur le train (précision ≥ 95 % pour `seuil_haut`, rappel ≥ 95 % pour `seuil_bas`).

### 4.4 Explicabilité
`reasons` = signaux déclenchés (messages rédigés) + jusqu'à 3 n-grammes dont la contribution (coef × valeur) pousse vers le verdict, message « Formulation proche d'arnaques connues : « … » ».

Réponse :
```json
{"verdict": "arnaque", "score": 0.94, "category": "usurpation_operateur",
 "category_score": 0.78, "reasons": [{"code": "...", "message": "..."}],
 "advice": "...", "model_version": "0.1.0.dev0"}
```

### 4.5 Évaluation
- Validation croisée `StratifiedGroupKFold(5)` sur le train ; test ouvert une fois.
- Benchmark : B0 majorité, B1 règles seules, B2 Naive Bayes mots, B3 SVM linéaire, **B4 modèle retenu**.
- Métriques : PR-AUC, F1, rappel à précision 95 %, matrice de confusion, F1 macro catégories ; IC 95 % par bootstrap (1 000 tirages).
- Analyse par source, faux positifs sur légitimes « notification_transaction », liste complète des erreurs.
- **Robustesse adversariale** : leetspeak, homoglyphes, espaces insérés, sans accents, majuscules, emojis → taux de détection avec vs sans normalisation.
- Objectifs pré-enregistrés (données réelles) : PR-AUC ≥ 0,95 ; rappel ≥ 90 % à précision 95 % ; FPR ≤ 5 % sur légitimes difficiles ; détection sous perturbation ≥ 85 %.

### 4.6 Sécurité du modèle
Sérialisation `skops` (jamais `pickle`) avec liste de types de confiance explicite. `manifest.json` : versions (modèle, dataset, scikit-learn), seuils, SHA-256 du fichier modèle, vérifié au chargement (fichier altéré → `ModelIntegrityError`). Model card publiée.

## 5. Produit

### 5.1 Bibliothèque
```python
from sikaguard import analyze, Analyzer

r = analyze("...")  # Result (dataclass) ; r.to_dict()
Analyzer(threshold_high=0.9, threshold_low=0.3).analyze_batch([...])  # noms anglais pour les devs
```
Dépendances : scikit-learn, numpy, scipy, skops. Python ≥ 3.10. Modèle chargé paresseusement une fois. CLI : `sikaguard "texte"`, `--json`, `-f fichier`.

### 5.2 API (FastAPI)
`POST /v1/analyze`, `POST /v1/analyze/batch` (≤ 100), `GET /v1/info`, `GET /health`.
- Aucun texte de SMS journalisé ni stocké (logs : longueur, verdict, latence) — testé.
- Validation 1–1 000 caractères ; 422 explicites ; 500 générique.
- Docker : image slim, utilisateur non-root, HEALTHCHECK.

### 5.3 Démo (Gradio)
Zone de texte, exemples cliquables, badge coloré, score, catégorie, raisons, conseil ; bandeau « rien n'est enregistré » ; flagging désactivé ; lien « Signaler une nouvelle arnaque » (issue form GitHub). Aucun logo d'opérateur ; mention « projet indépendant, non affilié ».

## 6. Qualité
- Tests : unitaires (normalize, signals), propriétés Hypothesis (aucun numéro ne survit), invariant de découpage, comportementaux type CheckList (invariance/direction), intégrité modèle, API (dont absence du texte dans les logs). Couverture ≥ 90 % sur `src/`.
- Outillage : venv + pip (compatible uv), ruff (dont règles `S` sécurité), mypy strict sur `src/`.
- CI GitHub Actions : lint, typage, tests Python 3.10–3.13, build, `pip-audit` ; release sur tag via PyPI Trusted Publishing + GHCR.
- Docs : README (EN) + README.fr.md, datasheet, model card, guide d'annotation, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CITATION.cff, ROADMAP, LICENSE.

## 7. Structure du dépôt
```
sikaguard/
├── src/sikaguard/{__init__,normalize,signals,features,model,result,cli}.py + assets/
├── data/{seed,raw(ignoré),processed}/ + scripts pipeline (sikaguard_data/)
├── training/{train,evaluate}.py → reports/
├── api/{app.py,Dockerfile}
├── demo/app.py
├── docs/ · tests/ · .github/
└── pyproject.toml · Makefile · README.md
```

## 8. Jalons (14 jours)
J1 fondations → J1–J6 collecte (humaine) → J2–J4 cœur → J5–J7 modélisation → J8–J9 produit → J9 gel des données → J10–J11 évaluation finale → J12–J14 publication.

## 9. Risques
Volume insuffisant (publier honnêtement, fusionner catégories < 15) ; licence 88milSMS (repli documenté) ; biais de source (métriques par source) ; données personnelles (masquage + relecture 100 %) ; marques (usage descriptif, aucun logo) ; nom PyPI pris (vérifier J1) ; dérive scikit-learn (manifeste + test CI) ; dérive de périmètre (ROADMAP).

## 10. Définition de « terminé » (v0.1.0)
Dataset HF + datasheet ; `pip install` fonctionnel Windows/Linux ; image Docker, API testée sans journalisation du texte ; démo en ligne ; benchmark + robustesse + model card avec IC ; CI verte, couverture ≥ 90 %, pip-audit propre ; docs complètes ; release `v0.1.0` taguée.

**Périmètre de cette première session d'implémentation :** tout ce qui est exécutable localement (code, tests, jeu d'amorçage, modèle `0.1.0.dev0`, rapports, API, Docker, démo locale, docs, CI). La collecte réelle et les publications (PyPI, HF, GitHub) nécessitent l'auteur et ses comptes.
