import pytest
from hypothesis import given
from hypothesis import strategies as st

from sikaguard.pii import (
    anonymize,
    defang,
    find_urls,
    has_phone_number,
    mask_codes,
    mask_emails,
    mask_phones,
    mask_refs,
    mask_urls,
    refang,
)


@pytest.mark.parametrize(
    "text",
    [
        "Appelle-moi au +225 07 08 09 10 11 stp",
        "Appelle-moi au 002250708091011 stp",
        "Appelle-moi au 07.08.09.10.11 stp",
        "Appelle-moi au 07-08-09-10-11 stp",
        "Appelle-moi au +221 77 123 45 67 stp",
        "Appelle-moi au (+226) 70 12 34 56 stp",
        "Appelle-moi au 70 12 34 56 stp",
        "Tel:0708091011",
    ],
)
def test_mask_phones_masks_west_african_numbers(text: str) -> None:
    masked = mask_phones(text)
    assert "<TEL>" in masked
    assert not has_phone_number(masked)


@pytest.mark.parametrize(
    "text",
    [
        "Vous avez recu 25 000 FCFA",
        "Gain de 10000000 F a retirer",
        "Solde: 1 500 000 FCFA",
        "Montant 10 000 000 francs",
        "Rendez-vous le 12/05/2025 a 14h",
        "Nouveau solde 125.000 F",
    ],
)
def test_mask_phones_keeps_amounts_and_dates(text: str) -> None:
    assert mask_phones(text) == text


_PREFIXES = st.sampled_from(["", "+225 ", "+225", "00225 ", "(+225) ", "+221 ", "00226", "+223 "])
_SEPARATORS = st.sampled_from([" ", ".", "-", ""])


@st.composite
def phone_numbers(draw: st.DrawFn) -> str:
    prefix = draw(_PREFIXES)
    sep = draw(_SEPARATORS)
    style = draw(st.sampled_from(["ci", "sn", "bf"]))
    if style == "ci":
        first = draw(st.sampled_from(["01", "05", "07", "27"]))
        groups = [first] + [draw(st.from_regex(r"\d{2}", fullmatch=True)) for _ in range(4)]
    elif style == "sn":
        first = draw(st.sampled_from(["70", "75", "76", "77", "78"]))
        groups = [
            first,
            draw(st.from_regex(r"\d{3}", fullmatch=True)),
            draw(st.from_regex(r"\d{2}", fullmatch=True)),
            draw(st.from_regex(r"\d{2}", fullmatch=True)),
        ]
    else:
        first = draw(st.sampled_from(["60", "70", "76", "78"]))
        groups = [first] + [draw(st.from_regex(r"\d{2}", fullmatch=True)) for _ in range(3)]
    return prefix + sep.join(groups)


@given(number=phone_numbers(), before=st.sampled_from(["Appelle ", "WhatsApp: ", "au "]))
def test_no_phone_number_survives_masking(number: str, before: str) -> None:
    text = f"{before}{number} stp"
    masked = mask_phones(text)
    assert "<TEL>" in masked
    assert not has_phone_number(masked)


@given(
    amount=st.integers(min_value=100, max_value=999_999_999),
    currency=st.sampled_from(["FCFA", "F", "francs", "XOF", "CFA"]),
)
def test_amounts_with_currency_are_never_masked(amount: int, currency: str) -> None:
    text = f"Vous avez recu {amount:,}".replace(",", " ") + f" {currency}."
    assert mask_phones(text) == text


def test_mask_codes() -> None:
    assert mask_codes("Votre code est 483920") == "Votre code est <CODE>"
    assert mask_codes("Code PIN: 1234.") == "Code PIN: <CODE>."
    assert mask_codes("<#> 483920 est votre code de verification") == (
        "<#> <CODE> est votre code de verification"
    )
    assert mask_codes("solde 125000 FCFA") == "solde 125000 FCFA"
    assert mask_codes("en 2025 on verra") == "en 2025 on verra"


def test_mask_refs() -> None:
    assert mask_refs("Ref: MP240930.1234.C56789.") == "Ref: <REF>."
    assert mask_refs("Transaction ID: CI2409301234 ok") == "Transaction ID: <REF> ok"
    assert mask_refs("Trans. MP240930.1234.C56789 reussie") == "Trans. <REF> reussie"
    assert mask_refs("Vous avez recu 25000FCFA") == "Vous avez recu 25000FCFA"


def test_mask_emails() -> None:
    assert mask_emails("ecrire a jean.kone@gmail.com svp") == "ecrire a <EMAIL> svp"


def test_find_urls() -> None:
    urls = find_urls("Cliquez bit.ly/abc3 ou www.exemple.com/x, ou http://41.202.10.5/login.")
    assert urls == ["bit.ly/abc3", "www.exemple.com/x", "http://41.202.10.5/login"]
    assert find_urls("M. Kone. Merci.") == []
    assert find_urls("ecrire a jean.kone@gmail.com") == []
    assert find_urls("hxxp://orange-bonus[.]xyz/gain") == ["http://orange-bonus.xyz/gain"]


def test_refang_and_defang() -> None:
    assert refang("hxxps://bit[.]ly/x") == "https://bit.ly/x"
    assert defang("Allez sur http://a.com/b.") == "Allez sur hxxp://a[.]com/b."
    once = defang("voir www.x.com et bit.ly/y")
    assert defang(once) == once
    assert once == "voir www[.]x[.]com et bit[.]ly/y"


def test_mask_urls() -> None:
    assert mask_urls("Cliquez hxxps://bit[.]ly/x vite") == "Cliquez <URL> vite"


def test_anonymize_full_message() -> None:
    raw = (
        "Orange Money: transfert de 5000 FCFA vers 0708091011 reussi. "
        "Ref: MP240930.1234.C56789. Code: 4821. Infos: www.orange-promo.xyz"
    )
    assert anonymize(raw) == (
        "Orange Money: transfert de 5000 FCFA vers <TEL> reussi. "
        "Ref: <REF>. Code: <CODE>. Infos: www[.]orange-promo[.]xyz"
    )
    assert anonymize(anonymize(raw)) == anonymize(raw)
