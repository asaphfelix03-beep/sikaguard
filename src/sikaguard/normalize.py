"""Anti-evasion text normalization.

Scammers deliberately disguise words to get past filters: ``0range M0ney``,
Cyrillic look-alike letters, ``c o d e``, zero-width characters, emojis inside
words. :func:`normalize` undoes these tricks and masks personal data with the
same placeholders as the dataset (see :mod:`sikaguard.pii`).
"""

from __future__ import annotations

import re
import unicodedata

from sikaguard import pii

__all__ = ["normalize"]

_HOMOGLYPHS = str.maketrans(
    {
        # Cyrillic
        "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
        "с": "c", "т": "t", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d",
        "ɡ": "g", "ӏ": "l", "ԛ": "q", "ԝ": "w", "ү": "y", "һ": "h",
        "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
        "С": "C", "Т": "T", "Х": "X", "І": "I", "Ј": "J", "Ѕ": "S", "У": "Y",
        # Greek
        "α": "a", "ο": "o", "ι": "i", "κ": "k", "ν": "v", "ρ": "p", "τ": "t", "υ": "u",
        "χ": "x", "Α": "A", "Β": "B", "Ε": "E", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
        "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ζ": "Z",
        # Latin look-alikes
        "ı": "i", "ȷ": "j",
    }
)  # fmt: skip

_LEET = str.maketrans("013457@$", "oieastas")
_LEET_CHARS = frozenset("013457@$")
_RUN_RE = re.compile(r"[a-z0-9@$]+")
_UNIT_SUFFIX_RE = re.compile(r"\d+[a-z]{1,4}")  # 25000f, 24h, 1ere, 5g
_NUMBERED_WORD_RE = re.compile(r"[a-z]+\d{2,}")  # promo2025, covid19
_SPACED_LETTERS_RE = re.compile(r"(?<!\w)(?:[a-z][ .\-_*]){2,}[a-z](?!\w)")
_SPACED_SEP_RE = re.compile(r"[ .\-_*]")
_REPEAT_RE = re.compile(r"([a-z!?.])\1{2,}")
_SPACES_RE = re.compile(r"\s+")
_DROPPED_CATEGORIES = frozenset({"Cf", "So", "Sk", "Cs", "Co"})


def _drop_invisible_and_symbols(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch) not in _DROPPED_CATEGORIES)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def _unleet_run(match: re.Match[str]) -> str:
    run = match.group(0)
    letters = sum(ch.isalpha() for ch in run)
    if letters < 2 or not _LEET_CHARS.intersection(run):
        return run
    if _UNIT_SUFFIX_RE.fullmatch(run) or _NUMBERED_WORD_RE.fullmatch(run):
        return run
    return run.translate(_LEET)


def _join_spaced_letters(match: re.Match[str]) -> str:
    return _SPACED_SEP_RE.sub("", match.group(0))


def normalize(text: str, *, enabled: bool = True) -> str:
    """Return the canonical form of ``text`` used by the model.

    With ``enabled=False`` the text is only lower-cased (used to measure what
    normalization brings in the robustness evaluation).
    """
    if not enabled:
        return text.lower()
    text = unicodedata.normalize("NFKC", text)
    text = _drop_invisible_and_symbols(text)
    text = pii.mask_emails(text)
    text = pii.mask_urls(text)
    text = pii.mask_refs(text)
    text = pii.mask_codes(text)
    text = pii.mask_phones(text)
    text = text.translate(_HOMOGLYPHS).lower()
    text = _strip_accents(text)
    text = _RUN_RE.sub(_unleet_run, text)
    text = _SPACED_LETTERS_RE.sub(_join_spaced_letters, text)
    text = _REPEAT_RE.sub(r"\1\1", text)
    return _SPACES_RE.sub(" ", text).strip()
