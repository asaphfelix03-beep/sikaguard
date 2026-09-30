import pytest

from sikaguard.signals import SIGNAL_CODES, SIGNAL_MESSAGES, detect_signals
from sikaguard.urls import inspect_url


def test_inspect_url_shortener() -> None:
    info = inspect_url("hxxp://bit[.]ly/x")
    assert info.host == "bit.ly"
    assert info.is_shortener


def test_inspect_url_ip() -> None:
    info = inspect_url("http://41.202.10.5:8080/login")
    assert info.is_ip
    assert info.is_suspect


def test_inspect_url_brand_lookalike_and_tld() -> None:
    info = inspect_url("https://orange-money-bonus.xyz/gain")
    assert info.brand_lookalike
    assert info.suspicious_tld
    assert info.is_suspect


def test_inspect_url_leet_brand_lookalike() -> None:
    assert inspect_url("0range.com").brand_lookalike


def test_inspect_url_punycode() -> None:
    assert inspect_url("http://xn--orang-9ua.com").is_punycode


def test_inspect_url_plain_brand_domain_is_not_suspect() -> None:
    info = inspect_url("https://www.orange.ci/fr/")
    assert info.host == "orange.ci"
    assert not info.is_suspect
    assert not info.is_shortener


POSITIVE = {
    "demande_code_secret": "Envoyez votre code secret au <TEL> pour valider",
    "demande_renvoi_argent": "je vous ai envoyé par erreur 25000F, renvoyez svp",
    "frais_a_payer": "Pour recevoir le lot, payez les frais de dossier de 5000F",
    "urgence": "URGENT: repondez dans les 24h",
    "menace_blocage": "Votre compte Orange Money sera bloqué",
    "gain_inattendu": "Félicitations! Vous avez gagné 500 000 FCFA",
    "promesse_gain_financier": "Doublez votre argent en 7 jours grâce au trading",
    "offre_emploi": "Nous recrutons des agents, salaire 150 000F",
    "lien_present": "Voir www.exemple.com",
    "lien_raccourci": "Cliquez bit.ly/abc",
    "lien_suspect": "Connectez-vous sur hxxp://mtn-bonus[.]xyz",
    "mention_operateur": "Votre compte MTN MoMo",
    "contact_numero": "Appelez vite le <TEL> pour retirer",
    "majuscules_excessives": "VOTRE COMPTE EST BLOQUE CONTACTEZ NOUS",
    "montant_present": "Vous avez reçu 25 000 FCFA",
}

NEGATIVE = {
    "demande_code_secret": "Orange Money ne vous demandera jamais votre code secret.",
    "demande_renvoi_argent": "Je suis bien arrivé, merci pour tout",
    "frais_a_payer": "Transfert reussi. Frais: 100 FCFA. Retrait sans frais ce weekend.",
    "urgence": "On se voit demain au marché",
    "menace_blocage": "Votre forfait internet est activé",
    "gain_inattendu": "Rendez-vous demain à 10h",
    "promesse_gain_financier": "Ton colis est arrivé",
    "offre_emploi": "Bonne fête maman",
    "lien_present": "Merci M. Kone. A demain.",
    "lien_raccourci": "Voir www.exemple.com",
    "lien_suspect": "Infos sur www.orange.ci",
    "mention_operateur": "Je t'appelle ce soir",
    "contact_numero": "Transfert vers <TEL> reussi.",
    "majuscules_excessives": "Bonjour, OK pour demain",
    "montant_present": "Bonjour comment tu vas",
}


def test_every_signal_has_message_and_examples() -> None:
    assert len(SIGNAL_CODES) == 15
    assert set(SIGNAL_MESSAGES) == set(SIGNAL_CODES)
    assert set(POSITIVE) == set(SIGNAL_CODES)
    assert set(NEGATIVE) == set(SIGNAL_CODES)


@pytest.mark.parametrize("code", SIGNAL_CODES)
def test_signal_positive(code: str) -> None:
    assert code in detect_signals(POSITIVE[code])


@pytest.mark.parametrize("code", SIGNAL_CODES)
def test_signal_negative(code: str) -> None:
    assert code not in detect_signals(NEGATIVE[code])


@pytest.mark.parametrize(
    "text",
    [
        "Tapez *144*4*6# puis entrez votre code PIN pour confirmer",
        "donne moi le code que tu as reçu par sms",
        "Envoie le code secret de ton compte wave au <TEL>",
        "N'oubliez pas d'envoyer votre code PIN au service client",
    ],
)
def test_code_requests(text: str) -> None:
    assert "demande_code_secret" in detect_signals(text)


@pytest.mark.parametrize(
    "text",
    [
        "Ne communiquez jamais votre code secret.",
        "Ne partagez pas ce code avec qui que ce soit.",
        "Votre code de verification est <CODE>. Ne le donnez a personne.",
    ],
)
def test_code_warnings_are_not_requests(text: str) -> None:
    assert "demande_code_secret" not in detect_signals(text)


def test_signals_follow_canonical_order() -> None:
    found = detect_signals("URGENT!!! Envoyez votre code secret au <TEL> sinon compte bloqué")
    assert found == [code for code in SIGNAL_CODES if code in found]


def test_signals_on_leetspeak_evasion() -> None:
    assert "demande_code_secret" in detect_signals("Envoyez votre c0de s3cret")


def test_signals_without_normalization_miss_evasion() -> None:
    assert "demande_code_secret" not in detect_signals(
        "Envoyez votre c0de s3cret", use_normalization=False
    )
