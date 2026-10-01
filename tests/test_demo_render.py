from demo.render import render_result
from sikaguard.result import ADVICE, Reason, Result


def make(verdict: str, category: str | None, message: str) -> Result:
    return Result(
        verdict=verdict,  # type: ignore[arg-type]
        score=0.87,
        category=category,
        category_score=0.6 if category else None,
        reasons=(Reason("x", message),),
        advice=ADVICE.get(category or verdict, ADVICE["legitime"]),
        model_version="test",
    )


def test_render_scam() -> None:
    html = render_result(make("arnaque", "faux_gain", "Le message annonce un gain."))
    assert "Arnaque probable" in html
    assert "Faux gain" in html
    assert "87 / 100" in html
    assert "Le message annonce un gain." in html


def test_render_escapes_html() -> None:
    html = render_result(make("suspect", "autre_arnaque", "<script>alert(1)</script>"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_legit_without_category() -> None:
    html = render_result(make("legitime", None, "ok"))
    assert "Aucun signe d" in html
    assert "Type :" not in html
