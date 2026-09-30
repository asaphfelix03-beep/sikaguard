"""Detection and masking of personal data and links in SMS text.

This module is shared by the dataset pipeline (``anonymize``) and by the
inference-time normalization (``sikaguard.normalize``), so that the model sees
exactly the same placeholders in training and in production.
"""

from __future__ import annotations

import re
from collections.abc import Callable

__all__ = [
    "anonymize",
    "defang",
    "find_urls",
    "has_phone_number",
    "mask_codes",
    "mask_emails",
    "mask_phones",
    "mask_refs",
    "mask_urls",
    "refang",
    "url_spans",
]

# --------------------------------------------------------------------------- URLs

_DOT = r"(?:\.|\[\.\]|\(\.\)|\[dot\])"
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_TLDS = (
    "com|net|org|info|biz|xyz|top|click|online|site|live|buzz|icu|shop|store|vip|club|"
    "link|app|io|me|co|ly|gd|cc|tk|ga|cf|gq|ml|pw|ci|sn|bf|bj|tg|cm|ne|gn|fr|africa"
)
_URL_RE = re.compile(
    rf"(?:(?:https?|hxxps?)(?::|\[:\])//[^\s<>\"']+"
    rf"|www{_DOT}[^\s<>\"']+"
    rf"|(?<![@\w.\-\[\]])(?:{_LABEL}{_DOT})+(?:{_TLDS})(?![\w-])(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
_TRAILING_PUNCT = ".,;:!?)»\"'"


def _clean_span(text: str, start: int, end: int) -> tuple[int, int]:
    while end > start and text[end - 1] in _TRAILING_PUNCT and not text[:end].endswith("[.]"):
        end -= 1
    return start, end


def url_spans(text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` spans of URLs, including defanged ones (``hxxp``, ``[.]``)."""
    return [_clean_span(text, m.start(), m.end()) for m in _URL_RE.finditer(text)]


def refang(text: str) -> str:
    """Turn defanged notation (``hxxp://a[.]com``) back into a plain URL."""
    text = re.sub(r"\[\.\]|\(\.\)|\[dot\]", ".", text, flags=re.IGNORECASE)
    text = text.replace("[:]", ":")
    return re.sub(r"hxxp", "http", text, flags=re.IGNORECASE)


def find_urls(text: str) -> list[str]:
    """Return the URLs found in ``text`` (refanged), in order of appearance."""
    return [refang(text[s:e]) for s, e in url_spans(text)]


def _replace_spans(text: str, spans: list[tuple[int, int]], fn: Callable[[str], str]) -> str:
    out: list[str] = []
    last = 0
    for start, end in spans:
        out.append(text[last:start])
        out.append(fn(text[start:end]))
        last = end
    out.append(text[last:])
    return "".join(out)


def _defang_url(url: str) -> str:
    url = refang(url)
    url = re.sub(r"^http", "hxxp", url, flags=re.IGNORECASE)
    return url.replace(".", "[.]")


def defang(text: str) -> str:
    """Make every URL in ``text`` non-clickable (``hxxp://a[.]com``). Idempotent."""
    return _replace_spans(text, url_spans(text), _defang_url)


def mask_urls(text: str, placeholder: str = "<URL>") -> str:
    """Replace every URL (plain or defanged) by ``placeholder``."""
    return _replace_spans(text, url_spans(text), lambda _: placeholder)


# ------------------------------------------------------------------------- emails

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def mask_emails(text: str, placeholder: str = "<EMAIL>") -> str:
    """Replace e-mail addresses by ``placeholder``."""
    return _EMAIL_RE.sub(placeholder, text)


# ------------------------------------------------------------------------- phones

_PHONE_CANDIDATE_RE = re.compile(r"(?<![\w+(])[+(]{0,2}\d(?:[ .\-()]{0,2}\d){7,14}(?!\d)")
_CURRENCY_AFTER_RE = re.compile(
    r"\s*(?:fcfa|cfa|xof|francs?\b|frs?\b|f\b|€|euros?\b|eur\b)", re.IGNORECASE
)
_THOUSANDS_RE = re.compile(r"[1-9]\d{0,2}(?:([ .])\d{3})(?:\1\d{3})*")


def _is_phone(text: str, match: re.Match[str]) -> bool:
    candidate = match.group(0)
    digits = sum(ch.isdigit() for ch in candidate)
    if not 8 <= digits <= 15:
        return False
    if _CURRENCY_AFTER_RE.match(text, match.end()):
        return False
    # "10 000 000" / "10.000.000" is an amount written with thousands separators.
    return not _THOUSANDS_RE.fullmatch(candidate)


def mask_phones(text: str, placeholder: str = "<TEL>") -> str:
    """Replace phone numbers (West-African formats, with or without prefix) by ``placeholder``.

    Amounts followed by a currency and numbers grouped by thousands are kept.
    """

    def repl(m: re.Match[str]) -> str:
        return placeholder if _is_phone(text, m) else m.group(0)

    return _PHONE_CANDIDATE_RE.sub(repl, text)


def has_phone_number(text: str) -> bool:
    """True if ``text`` still contains something that looks like a phone number."""
    return any(_is_phone(text, m) for m in _PHONE_CANDIDATE_RE.finditer(text))


# -------------------------------------------------------------- transaction refs

_REF_KEYWORD_RE = re.compile(
    r"(?i)\b(transaction\s+id|trans(?:action)?\s*id|id\s+transaction|txn(?:\s*id)?"
    r"|ref(?:erence)?|id)\b(\s*[:#.]?\s*)([a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?)"
)
_TOKEN_RE = re.compile(r"(?<![\w<\[])[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?(?![\w>\]])")
_AMOUNT_TOKEN_RE = re.compile(r"\d[\d.,]*(?:fcfa|cfa|xof|francs?|frs?|f)", re.IGNORECASE)


def _count(text: str, pred: Callable[[str], bool]) -> int:
    return sum(1 for ch in text if pred(ch))


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in spans)


def mask_refs(text: str, placeholder: str = "<REF>") -> str:
    """Replace transaction identifiers by ``placeholder``.

    Two rules: a token following a keyword (``Ref:``, ``Transaction ID``...) that
    contains at least 4 digits, and any stand-alone token of 8+ characters mixing
    at least 5 digits and one letter (``MP240930.1234.C56789``). Amounts
    (``25000FCFA``) and URLs are left untouched.
    """

    def keyword_repl(m: re.Match[str]) -> str:
        if _count(m.group(3), str.isdigit) >= 4:
            return f"{m.group(1)}{m.group(2)}{placeholder}"
        return m.group(0)

    text = _REF_KEYWORD_RE.sub(keyword_repl, text)
    spans = url_spans(text)

    def mixed_repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        if (
            len(tok) >= 8
            and _count(tok, str.isdigit) >= 5
            and _count(tok, str.isalpha) >= 1
            and not _AMOUNT_TOKEN_RE.fullmatch(tok)
            and not _inside(m.start(), spans)
        ):
            return placeholder
        return tok

    return _TOKEN_RE.sub(mixed_repl, text)


# -------------------------------------------------------------------------- codes

_NOT_CURRENCY = r"(?!\s*(?:fcfa|cfa|xof|francs?\b|frs?\b|f\b))"
_CODE_AFTER_RE = re.compile(
    r"(?i)\b(code(?:\s+(?:secret|pin|otp|confidentiel|de\s+[a-z]+))?|pin|otp"
    r"|mot\s+de\s+passe|mdp|password)\b([^\d\n<]{0,25}?)(?<!\d)(\d{4,8})(?!\d)" + _NOT_CURRENCY
)
_CODE_BEFORE_RE = re.compile(
    r"(?i)(?<![\d\w])(\d{4,8})(?!\d)"
    r"(\s+(?:est|is)\s+(?:votre|ton|your)\s+(?:code|otp|pin|mot\s+de\s+passe))"
)


def mask_codes(text: str, placeholder: str = "<CODE>") -> str:
    """Replace secret codes (PIN, OTP) that are introduced by a keyword by ``placeholder``."""
    text = _CODE_AFTER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{placeholder}", text)
    return _CODE_BEFORE_RE.sub(lambda m: f"{placeholder}{m.group(2)}", text)


# ---------------------------------------------------------------------- pipeline


def anonymize(text: str) -> str:
    """Anonymize a raw SMS for publication in the dataset. Idempotent.

    Masks e-mails, transaction references, secret codes and phone numbers, and
    defangs links. Names of people must be replaced by ``<NOM>`` by the
    annotator (they cannot be detected reliably).
    """
    text = mask_emails(text)
    text = mask_refs(text)
    text = mask_codes(text)
    text = mask_phones(text)
    return defang(text)
