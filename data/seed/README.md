# data/seed — jeu d'amorçage

`seed_sms.csv` contient **407 SMS rédigés à la main** d'après des schémas
d'arnaque publiquement documentés et le format des notifications des
opérateurs Mobile Money d'Afrique de l'Ouest. Ce ne sont **pas** des SMS réels
collectés : toutes les lignes portent `source_type=amorcage` et
`derive_de_modele=true`.

Ce jeu sert à faire fonctionner tout le système de bout en bout (pipeline,
entraînement, évaluation, API, démo) **avant** la collecte réelle. Le modèle
entraîné uniquement dessus (`0.1.0.dev0`) était marqué « not for production ».
Depuis `0.1.0.dev1`, il est complété par les sources réelles de `data/sources/`.

La collecte réelle suit `docs/annotation_guide.md` et se place dans
`data/raw/` (privé). `python -m sikaguard_lab.build` fusionne les deux.
