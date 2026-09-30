"""Shared fixtures: a tiny, fast model trained on a handful of SMS."""

from __future__ import annotations

from pathlib import Path

import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from sikaguard.features import build_features
from sikaguard.model import LoadedModel, load_model, save_model

TINY_SCAMS = [
    ("Envoyez votre code secret au <TEL> sinon votre compte Orange Money sera bloqué",
     "usurpation_operateur"),
    ("Service client MTN: confirmez votre code PIN au <TEL> pour éviter la suspension",
     "usurpation_operateur"),
    ("Félicitations vous avez gagné 500000F à la tombola, payez les frais de dossier",
     "faux_gain"),
    ("Bravo! Vous êtes le gagnant du tirage au sort, envoyez 5000F de frais", "faux_gain"),
    ("Je vous ai envoyé 25000F par erreur, renvoyez svp c'est urgent", "faux_transfert"),
    ("Maman j'ai fait un transfert de 10000F par erreur sur ton numero renvoie stp",
     "faux_transfert"),
]  # fmt: skip
TINY_LEGIT = [
    "Transfert de 5000 FCFA vers <TEL> reussi. Nouveau solde 12000 FCFA.",
    "Je suis arrivé à la maison, on se voit demain",
    "Votre code de verification est <CODE>. Ne le partagez avec personne.",
    "Vous avez recu 10000 FCFA de <TEL>. Nouveau solde 45000 FCFA.",
    "Ok pour ce soir, je t'appelle après le travail",
    "Rechargez 1000F et profitez de 2Go valables 7 jours",
]


def train_tiny(directory: Path) -> LoadedModel:
    texts = [t for t, _ in TINY_SCAMS] + TINY_LEGIT
    labels = [1] * len(TINY_SCAMS) + [0] * len(TINY_LEGIT)
    binary = Pipeline([("features", build_features()), ("clf", LogisticRegression(C=10.0))])
    binary.fit(texts, labels)
    category = Pipeline([("features", build_features()), ("clf", LogisticRegression(C=10.0))])
    category.fit([t for t, _ in TINY_SCAMS], [c for _, c in TINY_SCAMS])
    save_model(
        binary,
        category,
        directory,
        model_version="test",
        dataset_version="test",
        threshold_high=0.7,
        threshold_low=0.3,
        not_for_production=True,
        training_data="unit-test fixture",
    )
    return load_model(directory)


@pytest.fixture(scope="session")
def tiny_model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("tiny_model")
    train_tiny(directory)
    return directory


@pytest.fixture(scope="session")
def tiny_model(tiny_model_dir: Path) -> LoadedModel:
    return load_model(tiny_model_dir)
