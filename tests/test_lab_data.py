import json
from collections import defaultdict
from pathlib import Path

import pytest

from sikaguard_lab.build import DATASET_FILE, STATS_FILE, main
from sikaguard_lab.dedup import assign_groups, drop_exact_duplicates, jaccard, shingles
from sikaguard_lab.schema import COLUMNS, RAW_COLUMNS, read_csv, validate_rows, write_csv
from sikaguard_lab.split import group_stratified_split


def raw_row(**overrides: str) -> dict[str, str]:
    row = {
        "text": "Vous avez gagné 500000F, payez les frais de dossier",
        "label": "arnaque",
        "category": "faux_gain",
        "operateur_cible": "aucun",
        "pays": "CI",
        "source_type": "amorcage",
        "date_observee": "",
        "derive_de_modele": "true",
        "confiance_annotation": "haute",
    }
    row.update(overrides)
    return row


# ------------------------------------------------------------------ validation


def test_valid_row() -> None:
    assert validate_rows([raw_row()]) == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"label": "spam"}, "label invalide"),
        ({"category": "otp"}, "incompatible"),
        ({"text": "  "}, "texte vide"),
        ({"text": "a" * 1001}, "trop long"),
        ({"text": "Appelle le 0708091011"}, "numéro"),
        ({"text": "Ecris a jean@gmail.com"}, "e-mail"),
        ({"text": "Clique sur http://bit.ly/x"}, "désamorcé"),
        ({"pays": "US"}, "pays"),
        ({"operateur_cible": "free"}, "operateur_cible"),
        ({"source_type": "blog"}, "source_type"),
        ({"derive_de_modele": "yes"}, "derive_de_modele"),
        ({"confiance_annotation": "basse"}, "confiance_annotation"),
        ({"date_observee": "2025-13"}, "date_observee"),
    ],
)
def test_invalid_rows(overrides: dict[str, str], message: str) -> None:
    errors = validate_rows([raw_row(**overrides)])
    assert any(message in e for e in errors), errors
    assert errors[0].startswith("ligne 2:")


def test_defanged_link_is_accepted() -> None:
    assert validate_rows([raw_row(text="Clique sur hxxp://bit[.]ly/x")]) == []


def test_missing_columns_and_empty() -> None:
    row = raw_row()
    del row["pays"]
    assert validate_rows([row]) == ["colonnes manquantes: ['pays']"]
    assert validate_rows([]) == ["aucune ligne"]


def test_processed_validation() -> None:
    row = {**raw_row(), "id": "sg-1", "group_id": "x", "split": "dev"}
    errors = validate_rows([row, row], processed=True)
    assert any("split invalide" in e for e in errors)
    assert any("group_id invalide" in e for e in errors)
    assert "identifiants dupliqués" in errors


def test_csv_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    write_csv(path, [raw_row(text='Texte, avec "guillemets"\net retour')], RAW_COLUMNS)
    assert read_csv(path) == [raw_row(text='Texte, avec "guillemets"\net retour')]
    assert b"\r\n" not in path.read_bytes()


# --------------------------------------------------------------------- dedup


def test_shingles_and_jaccard() -> None:
    assert shingles("abc") == {"abc"}
    assert "vous " in shingles("Vous avez")
    assert jaccard(set(), set()) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_drop_exact_duplicates_uses_normalization() -> None:
    rows = [raw_row(text="Félicitations!"), raw_row(text="felicitations!"), raw_row(text="autre")]
    kept, removed = drop_exact_duplicates(rows)
    assert removed == 1
    assert [r["text"] for r in kept] == ["Félicitations!", "autre"]


def test_assign_groups_near_duplicates() -> None:
    texts = [
        "Je vous ai envoye 25000F par erreur sur votre compte, renvoyez svp",
        "Rendez-vous demain à 10h au marché de Cocody",
        "Je vous ai envoye 30000F par erreur sur votre compte, renvoyez svp",
        "Je vous ai envoye 30000F par erreur sur votre compte, renvoyez svp merci",
    ]
    groups = assign_groups(texts)
    assert groups[0] == groups[2] == groups[3]
    assert groups[1] != groups[0]
    assert groups == [0, 1, 0, 0]
    assert assign_groups([]) == []


# --------------------------------------------------------------------- split


def test_group_split_never_leaks() -> None:
    strata = ["a"] * 50 + ["b"] * 50
    groups = [i // 3 for i in range(100)]
    split = group_stratified_split(strata, groups, test_size=0.2, seed=1)
    by_group: dict[int, set[str]] = defaultdict(set)
    for g, s in zip(groups, split, strict=True):
        by_group[g].add(s)
    assert all(len(v) == 1 for v in by_group.values())
    n_test = split.count("test")
    assert 12 <= n_test <= 28
    assert {strata[i] for i, s in enumerate(split) if s == "test"} == {"a", "b"}


def test_split_is_deterministic_and_validates_size() -> None:
    strata = ["a", "b"] * 20
    groups = list(range(40))
    assert group_stratified_split(strata, groups, seed=3) == group_stratified_split(
        strata, groups, seed=3
    )
    with pytest.raises(ValueError, match="test_size"):
        group_stratified_split(strata, groups, test_size=1.5)


# --------------------------------------------------------------------- build


def test_build_end_to_end(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    rows = []
    for i in range(20):
        rows.append(raw_row(text=f"Vous avez gagné {i}00000F à la tombola numero {i}, payez"))
        rows.append(
            raw_row(
                text=f"Rendez-vous demain à {i}h chez tonton {'abcdefghijklmnopqrst'[i]}",
                label="legitime",
                category="personnel",
            )
        )
    rows.append(rows[0])  # exact duplicate
    write_csv(seed / "seed.csv", rows, RAW_COLUMNS)
    out = tmp_path / "out"
    assert (
        main(["--seed-dir", str(seed), "--raw-dir", str(tmp_path / "none"), "--out", str(out)]) == 0
    )
    data = read_csv(out / DATASET_FILE)
    assert list(data[0]) == list(COLUMNS)
    assert len(data) == 40
    assert data[0]["id"] == "sg-00001"
    stats = json.loads((out / STATS_FILE).read_text(encoding="utf-8"))
    assert stats["n_exact_duplicates_removed"] == 1
    assert stats["by_label"] == {"arnaque": 20, "legitime": 20}
    assert validate_rows(data, processed=True) == []


def test_build_rejects_invalid_data(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seed = tmp_path / "seed"
    write_csv(seed / "bad.csv", [raw_row(text="Appelle le 0708091011")], RAW_COLUMNS)
    assert main(["--seed-dir", str(seed), "--raw-dir", str(seed), "--out", str(tmp_path)]) == 1
    assert "numéro" in capsys.readouterr().err


def test_build_without_data(tmp_path: Path) -> None:
    assert main(["--seed-dir", str(tmp_path / "a"), "--raw-dir", str(tmp_path / "b")]) == 1
