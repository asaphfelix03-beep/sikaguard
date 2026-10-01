from pathlib import Path

import pytest

from sikaguard_lab.import_88milsms import iter_posts, main, sample
from sikaguard_lab.schema import read_csv, validate_rows

TEI = "http://www.tei-c.org/ns/1.0"


def _post(i: int, body: str) -> str:
    return (
        f'<post xml:id="p{i}" when-iso="2011-09-1{i % 10}T08:00:00" type="sms"><p>{body}</p></post>'
    )


def _anon(tag: str) -> str:
    return f'<fs type="anonymisation"><f name="anonyString"><string>{tag}</string></f></fs>'


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    posts = [
        _post(
            1,
            "Coucou "
            + _anon("[_forename_]")
            + ' on se voit ce soir <distinct type="emoticon">:)</distinct>',
        ),
        _post(2, "Rappelle moi au " + _anon("[_tel_]") + " stp, c'est pour demain"),
        _post(3, "Je suis a " + _anon("[_address_]") + " depuis une heure"),  # rejected tag
        _post(4, "ok"),  # too short
        _post(5, "Envoie ce message à 10 personnes sinon malheur"),  # chain letter
        _post(6, "Regarde www.exemple.com c'est drole"),  # link
    ]
    posts += [_post(10 + i, f"Message numero {i} pour le test, a plus tard") for i in range(20)]
    xml = f'<TEI xmlns="{TEI}"><text><body><div>{"".join(posts)}</div></body></text></TEI>'
    path = tmp_path / "corpus.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_iter_posts_maps_and_rejects_tags(corpus: Path) -> None:
    texts = [t for t, _ in iter_posts(corpus)]
    assert "Coucou <NOM> on se voit ce soir :)" in texts
    assert "Rappelle moi au <TEL> stp, c'est pour demain" in texts
    assert not any("depuis une heure" in t for t in texts)
    assert not any(t == "ok" for t in texts)


def test_sample_is_disjoint_and_valid(corpus: Path) -> None:
    train, held_out = sample(corpus, 5, 10, seed=1)
    assert len(train) == 5 and len(held_out) == 10
    assert not {r["text"] for r in train} & {r["text"] for r in held_out}
    assert validate_rows(train) == [] and validate_rows(held_out) == []
    all_texts = " ".join(r["text"] for r in train + held_out)
    assert "Envoie ce message" not in all_texts
    assert "www.exemple" not in all_texts
    assert train[0]["source_type"] == "corpus_recherche"
    assert train[0]["date_observee"].startswith("2011-09")


def test_sample_too_small(corpus: Path) -> None:
    with pytest.raises(ValueError, match="usable SMS"):
        sample(corpus, 50, 50)


def test_main_writes_files(corpus: Path, tmp_path: Path) -> None:
    train_out, eval_out = tmp_path / "s.csv", tmp_path / "e.csv"
    args = ["--xml", str(corpus), "--n-train", "4", "--n-eval", "6"]
    assert main([*args, "--train-out", str(train_out), "--eval-out", str(eval_out)]) == 0
    assert len(read_csv(train_out)) == 4
    assert len(read_csv(eval_out)) == 6
