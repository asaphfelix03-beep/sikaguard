import json

import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from sikaguard.explain import signal_weights, top_terms
from sikaguard.features import SignalTransformer, TextNormalizer, build_features
from sikaguard.normalize import normalize
from sikaguard.result import ADVICE, SCAM_CATEGORIES, Reason, Result
from sikaguard.signals import SIGNAL_CODES

SCAMS = [
    "Envoyez votre code secret au <TEL> sinon votre compte sera bloqué",
    "Félicitations vous avez gagné 500000F, payez les frais de dossier",
    "Je vous ai envoyé 25000F par erreur, renvoyez svp",
]
LEGIT = [
    "Transfert de 5000 FCFA vers <TEL> reussi. Nouveau solde 12000 FCFA.",
    "Je suis arrivé à la maison, on se voit demain",
    "Votre code de verification est <CODE>. Ne le partagez avec personne.",
]


@pytest.fixture(scope="module")
def tiny_pipeline() -> Pipeline:
    pipe = Pipeline([("features", build_features()), ("clf", LogisticRegression(C=10.0))])
    pipe.fit(SCAMS + LEGIT, [1, 1, 1, 0, 0, 0])
    return pipe


def test_signal_transformer_shape_and_names() -> None:
    matrix = SignalTransformer().fit_transform(SCAMS)
    assert matrix.shape == (3, len(SIGNAL_CODES))
    assert list(SignalTransformer().get_feature_names_out()) == list(SIGNAL_CODES)
    assert matrix[0, SIGNAL_CODES.index("demande_code_secret")] == 1.0


def test_text_normalizer_disabled() -> None:
    assert TextNormalizer(normalize=False).fit_transform(["0range"]) == ["0range"]
    assert TextNormalizer().fit_transform(["0range"]) == ["orange"]
    assert list(TextNormalizer().get_feature_names_out()) == ["text"]


def test_build_features_blocks(tiny_pipeline: Pipeline) -> None:
    names = tiny_pipeline.named_steps["features"].get_feature_names_out()
    prefixes = {str(n).split("__", 1)[0] for n in names}
    assert prefixes == {"chars", "words", "signals"}
    assert "words__<tel>" in set(map(str, names))


def test_top_terms_toward_scam(tiny_pipeline: Pipeline) -> None:
    terms = top_terms(tiny_pipeline, SCAMS[0], toward=1, k=3)
    assert 1 <= len(terms) <= 3
    assert all("<" not in t for t in terms)
    assert all(t in normalize(SCAMS[0]) for t in terms)


def test_top_terms_toward_legit(tiny_pipeline: Pipeline) -> None:
    terms = top_terms(tiny_pipeline, LEGIT[1], toward=-1, k=2)
    assert terms
    assert all(t in normalize(LEGIT[1]) for t in terms)


def test_signal_weights(tiny_pipeline: Pipeline) -> None:
    weights = signal_weights(tiny_pipeline)
    assert set(weights) == set(SIGNAL_CODES)
    assert weights["demande_code_secret"] > 0


def test_result_to_dict_is_json_serializable() -> None:
    result = Result(
        verdict="arnaque",
        score=0.9,
        category="faux_gain",
        category_score=0.7,
        reasons=(Reason("gain_inattendu", "msg"),),
        advice=ADVICE["faux_gain"],
        model_version="x",
    )
    assert result.is_scam
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["reasons"] == [{"code": "gain_inattendu", "message": "msg"}]


def test_advice_covers_every_scam_category_and_verdict() -> None:
    assert set(SCAM_CATEGORIES) | {"suspect", "legitime"} == set(ADVICE)


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("code secret", True),
        ("secret au", True),
        ("au", False),
        ("000 f", False),
        ("sur ton", False),
        ("renvoie", True),
        ("2go", False),
    ],
)
def test_is_informative(term: str, expected: bool) -> None:
    from sikaguard.explain import is_informative

    assert is_informative(term) is expected


def test_top_terms_are_not_redundant(tiny_pipeline: Pipeline) -> None:
    terms = top_terms(tiny_pipeline, SCAMS[0], toward=1, k=5)
    for i, a in enumerate(terms):
        for b in terms[i + 1 :]:
            assert not set(a.split()) <= set(b.split())
            assert not set(b.split()) <= set(a.split())


def test_fast_transform_matches_feature_union(tiny_pipeline: Pipeline) -> None:
    from sikaguard.features import fast_transform

    union = tiny_pipeline.named_steps["features"]
    texts = SCAMS + LEGIT + ["Texte jamais vu 🎉 avec <TEL>"]
    expected = union.transform(texts).toarray()
    assert (fast_transform(union, texts).toarray() == expected).all()
