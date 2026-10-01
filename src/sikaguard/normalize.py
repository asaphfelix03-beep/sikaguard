"""Anti-evasion text normalization.

Scammers deliberately disguise words to get past filters: ``0range M0ney``,
Cyrillic look-alike letters, ``c o d e``, zero-width characters, emojis inside
words. :func:`normalize` undoes these tricks and masks personal data with the
same placeholders as the dataset (see :mod:`sikaguard.pii`).
"""

from __future__ import annotations

import functools
import re
import unicodedata

from sikaguard import pii

__all__ = ["fold_characters", "normalize"]

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
        # Typographic apostrophes and quotes
        "’": "'", "‘": "'", "ʼ": "'",
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


#: Words used to re-split letters that were spaced out across several words
#: ("c o d e s e c r e t" -> "codesecret" -> "code secret").
_SEGMENT_LEXICON = frozenset(
    """
    code secret pin mot de passe otp orange money mtn momo moov wave flooz compte bloque
    bloquer suspendu urgent envoyez envoie envoyer envoi gagne gagner gagnant felicitations
    frais cliquez clique lien votre ton vos au le la les un une par erreur renvoyez renvoie
    service client numero argent cadeau bonus tombola retrait transfert depot solde
    verification confirmer confirmez activer debloquer gratuit offre promo payez payer vite
    appelez appelle contactez whatsapp ici maintenant
    """.split()  # noqa: SIM905 - a word list reads better than quoted strings
)
_MAX_WORD = max(len(w) for w in _SEGMENT_LEXICON)


def _segment(joined: str) -> str | None:
    """Split ``joined`` into the fewest lexicon words, or ``None`` if impossible."""
    best: list[list[str] | None] = [[]] + [None] * len(joined)
    for end in range(1, len(joined) + 1):
        for start in range(max(0, end - _MAX_WORD), end):
            prefix = best[start]
            word = joined[start:end]
            if prefix is not None and word in _SEGMENT_LEXICON:
                candidate = [*prefix, word]
                current = best[end]
                if current is None or len(candidate) < len(current):
                    best[end] = candidate
    words = best[-1]
    return " ".join(words) if words else None


def _join_spaced_letters(match: re.Match[str]) -> str:
    joined = _SPACED_SEP_RE.sub("", match.group(0))
    return _segment(joined) or joined


def fold_characters(text: str, *, homoglyphs: bool = True) -> str:
    """NFKC, drop invisible characters and emojis, map look-alike letters to Latin.

    Case is preserved. The homoglyph mapping is one character to one character,
    so ``fold_characters(t)`` and ``fold_characters(t, homoglyphs=False)`` have
    the same length and aligned positions.
    """
    text = _drop_invisible_and_symbols(unicodedata.normalize("NFKC", text))
    return text.translate(_HOMOGLYPHS) if homoglyphs else text


def normalize(text: str, *, enabled: bool = True) -> str:
    """Return the canonical form of ``text`` used by the model.

    With ``enabled=False`` the text is only lower-cased (used to measure what
    normalization brings in the robustness evaluation). Results are cached:
    the same SMS is normalized by several feature blocks.
    """
    return _normalize_cached(text, enabled)


@functools.lru_cache(maxsize=4096)
def _normalize_cached(text: str, enabled: bool) -> str:
    if not enabled:
        return text.lower()
    # Look-alike letters are folded *before* link detection, otherwise a link
    # written with Cyrillic letters ("hххр://...") would escape <url> masking.
    text = fold_characters(text)
    text = pii.mask_emails(text)
    text = pii.mask_urls(text)
    text = pii.mask_refs(text)
    text = pii.mask_codes(text)
    text = pii.mask_phones(text)
    text = text.lower()
    text = _strip_accents(text)
    text = _RUN_RE.sub(_unleet_run, text)
    text = _SPACED_LETTERS_RE.sub(_join_spaced_letters, text)
    text = _REPEAT_RE.sub(r"\1\1", text)
    return _SPACES_RE.sub(" ", text).strip()
