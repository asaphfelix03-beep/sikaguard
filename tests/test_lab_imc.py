import random

from sikaguard.signals import detect_signals
from sikaguard_lab.import_imc25 import category, convert, operator, rewrite_tags
from sikaguard_lab.schema import validate_rows


def _row(text: str, scam_type: str = "delivery", **extra: str) -> dict[str, str]:
    row = {
        "time": "2023-05-19",
        "text": text,
        "language": "French",
        "url_shortener": "",
        "named_entity": "",
        "scam_type": scam_type,
        "original_network_country": "FRA",
    }
    row.update(extra)
    return row


def test_rewrite_tags_maps_every_tag() -> None:
    rng = random.Random(0)
    out = rewrite_tags(
        "<NAMED_ENTITY>: colis <NUMERO_COLIS> le <DATE_TIME>, appelez <PHONE_NUMBER> ou <URL>",
        "",
        rng,
    )
    assert "<NOM>" in out and "<REF>" in out and "<TEL>" in out and "<URL>" in out
    assert "<DATE_TIME>" not in out and "<NUMERO_COLIS>" not in out
    assert any(ch.isdigit() for ch in out.split("le ")[1][:5])


def test_rewrite_url_with_known_shortener() -> None:
    out = rewrite_tags("Suivez <URL>", "https://bit.ly", random.Random(1))
    assert out.startswith("Suivez bit[.]ly/")


def test_category_and_operator_mapping() -> None:
    assert category("banking", "x") == "usurpation_operateur"
    assert category("delivery", "x") == "phishing_lien"
    assert category("government", "payez sur <URL>") == "phishing_lien"
    assert category("government", "rappelez nous") == "autre_arnaque"
    assert category("hey mum/dad", "maman") == "autre_arnaque"
    assert operator("banking", "") == "banque"
    assert operator("telecom", "Orange") == "orange"
    assert operator("telecom", "sfr") == "autre"


def test_convert_filters_language_type_duplicates_and_exclusions() -> None:
    rows = [
        _row("Votre colis est en attente: <URL>"),
        _row("Votre colis est en attente: <URL>"),  # duplicate
        _row("Promo -50% sur tout", scam_type="spam"),  # marketing, not kept
        _row("Votre RDV est retardé de 10 min", scam_type="others"),  # excluded by review
        _row("Your parcel is waiting", language="English"),
        _row("ANTAI : amende impayée de 35€, payez sur <URL>", scam_type="government",
             original_network_country="BEL"),
    ]  # fmt: skip
    out, counts = convert(rows, excluded={"Votre RDV est retardé de 10 min"})
    assert [r["text"] for r in out] == [
        "Votre colis est en attente: <URL>",
        "ANTAI : amende impayée de 35€, payez sur <URL>",
    ]
    assert counts == {"french": 5, "other_scam_type": 1, "excluded_by_review": 1, "duplicates": 1}
    assert out[1]["pays"] == "BE" and out[0]["date_observee"] == "2023-05"
    assert validate_rows(out) == []


def test_masked_link_counts_as_a_link() -> None:
    assert "lien_present" in detect_signals("Payez votre amende sur <URL>")


def test_overrides_fix_text_and_category() -> None:
    rows = [_row("ous avez recu 15500 FCFA de Jean Kone. Transaction <URL>", scam_type="others")]
    overrides = {
        "ous avez recu 15500 FCFA de Jean Kone. Transaction <URL>": {
            "text": "Vous avez recu 15500 FCFA de <NOM>. Transaction <REF>",
            "category": "faux_transfert",
            "operateur_cible": "aucun",
            "pays": "XX",
        }
    }
    out, _ = convert(rows, excluded=set(), overrides=overrides)
    assert out[0]["text"] == "Vous avez recu 15500 FCFA de <NOM>. Transaction <REF>"
    assert out[0]["category"] == "faux_transfert"
    assert out[0]["pays"] == "XX"
