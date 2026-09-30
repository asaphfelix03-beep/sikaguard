"""Behavioral tests of the bundled model (CheckList methodology, Ribeiro et al. 2020).

These tests pin *capabilities* rather than exact scores: minimum functionality
(canonical cases), invariance (irrelevant edits keep the verdict) and
directional expectations (a red flag raises the score). None of the texts below
is in the seed dataset.
"""

from __future__ import annotations

import pytest

from sikaguard.analyzer import Analyzer
from sikaguard.model import load_model


@pytest.fixture(scope="module")
def az() -> Analyzer:
    return Analyzer(model=load_model())


SCAMS = {
    "usurpation_operateur": (
        "Service client Orange Money: votre compte sera suspendu ce soir. "
        "Envoyez votre code secret au 0701020304 pour le garder actif."
    ),
    "faux_transfert": "Je t'ai envoyé 20000 par erreur sur ton wave, renvoie stp c'est urgent",
    "faux_gain": "Félicitations! Vous avez gagné 1 000 000 F. Payez 5000 F de frais pour recevoir.",
    "phishing_lien": "Cliquez ici pour débloquer votre compte: http://mtn-momo-secure.xyz/login",
    "investissement_emploi": "Doublez votre argent en 7 jours, investissez 50 000 F maintenant",
}

LEGIT = [
    "Vous avez reçu 15 000 FCFA de KOUASSI. Nouveau solde: 17 500 FCFA.",
    "Votre code de vérification est 482913. Ne le partagez avec personne.",
    "On se voit demain à la maison, n'oublie pas le pain",
    "Maman envoie moi 5000 pour le transport stp",
    "Orange: profitez de 2Go à 500F valables 3 jours en tapant #111#.",
]


@pytest.mark.parametrize("category", sorted(SCAMS))
def test_canonical_scams(az: Analyzer, category: str) -> None:
    result = az.analyze(SCAMS[category])
    assert result.verdict == "arnaque"
    assert result.category == category
    assert result.reasons


@pytest.mark.parametrize("text", LEGIT)
def test_canonical_legit(az: Analyzer, text: str) -> None:
    assert az.analyze(text).verdict == "legitime"


@pytest.mark.parametrize(
    ("template", "values"),
    [
        (
            "Je vous ai envoyé {} F par erreur sur votre compte, renvoyez svp",
            ["5000", "25 000", "150.000"],
        ),
        (
            "Vous avez reçu {} FCFA de KONE. Nouveau solde: 30 000 FCFA.",
            ["2000", "10 000", "75 000"],
        ),
        (
            "Tonton c'est {}, envoie-moi vite 20 000 F sur ce numéro, je suis bloqué",
            ["Awa", "Moussa", "Yao"],
        ),
    ],
)
def test_invariance_amounts_and_names(az: Analyzer, template: str, values: list[str]) -> None:
    verdicts = {az.analyze(template.format(v)).verdict for v in values}
    assert len(verdicts) == 1


@pytest.mark.parametrize(
    "base",
    [
        "Bonjour, votre compte a été mis à jour.",
        "Bonsoir, c'est le service client.",
        "Votre transfert est en cours de traitement.",
    ],
)
def test_direction_asking_for_code_raises_score(az: Analyzer, base: str) -> None:
    before = az.analyze(base).score
    after = az.analyze(base + " Envoyez votre code secret au 0701020304.").score
    assert after > before


@pytest.mark.parametrize(
    "disguised",
    [
        "Env0yez v0tre c0de s3cret au service client 0range M0ney",  # leetspeak
        "Envoyez votre соde secret au service client Оrange Money",  # Cyrillic homoglyphs
        "Envoyez votre c o d e s e c r e t au service client",  # spaced letters
        "Envoyez votre co​de sec​ret au service client",  # zero-width characters
        "ENVOYEZ VOTRE CODE SECRET AU SERVICE CLIENT ORANGE MONEY",  # upper case
    ],
)
def test_disguised_scams_are_not_legit(az: Analyzer, disguised: str) -> None:
    assert az.analyze(disguised).verdict != "legitime"


def test_bundled_model_is_flagged_seed(az: Analyzer) -> None:
    info = az.info()
    assert info["not_for_production"] is True
    assert info["threshold_low"] < info["threshold_high"]
