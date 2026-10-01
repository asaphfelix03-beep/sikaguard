import pytest

from sikaguard.normalize import normalize

CASES = [
    ("0range M0ney", "orange money"),
    ("c0de s3cret", "code secret"),
    ("Оrange", "orange"),  # Cyrillic capital O
    ("Моnеy", "money"),  # Cyrillic М, о, е
    ("c o d e", "code"),
    ("c o d e s e c r e t", "code secret"),  # letters spaced across two words
    ("o r a n g e m o n e y", "orange money"),
    ("x y z w", "xyzw"),  # unknown words are simply joined
    ("S.V.P envoyez", "svp envoyez"),
    ("URGEEEENT!!!!", "urgeent!!"),
    ("Félicitations", "felicitations"),
    ("fél​icitations", "felicitations"),
    ("gag🎉né", "gagne"),
    ("25000F", "25000f"),
    ("1ère fois", "1ere fois"),
    ("promo2025 24h 5G", "promo2025 24h 5g"),
    ("appelez +225 0708091011", "appelez <tel>"),
    ("Cliquez hxxps://bit[.]ly/x", "cliquez <url>"),
    ("Payez ici: hххр://faux[.]click", "payez ici: <url>"),  # Cyrillic link
    ("Votre code est 483920", "votre code est <code>"),
    ("écrire à jean.kone@gmail.com", "ecrire a <email>"),
    ("<TEL> <NOM>", "<tel> <nom>"),
    ("  trop   d'espaces \n ici ", "trop d'espaces ici"),
    ("l’argent", "l'argent"),  # typographic apostrophe
    ("𝐎𝐑𝐀𝐍𝐆𝐄", "orange"),  # mathematical bold, handled by NFKC
    ("ＷＡＶＥ", "wave"),  # full-width
]


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(("raw", "_"), CASES)
def test_normalize_is_idempotent(raw: str, _: str) -> None:
    once = normalize(raw)
    assert normalize(once) == once


def test_disabled_normalization_only_lowercases() -> None:
    assert normalize("0range M0ney", enabled=False) == "0range m0ney"


def test_normalize_empty_and_symbols_only() -> None:
    assert normalize("") == ""
    assert normalize("🎉🎉🎉") == ""
