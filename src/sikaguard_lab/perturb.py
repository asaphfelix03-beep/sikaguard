"""Adversarial perturbations that mimic how scammers disguise their SMS.

Every function takes ``(text, rng)`` and returns a disguised text. They are
deterministic for a seeded :class:`random.Random`.
"""

from __future__ import annotations

import random
import re
import unicodedata
from collections.abc import Callable

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]{4,}")
_LEET = {"o": "0", "e": "3", "a": "4", "i": "1", "s": "5"}
_CYRILLIC = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "A": "А", "E": "Е",
             "O": "О", "P": "Р", "C": "С", "X": "Х"}  # fmt: skip
_EMOJIS = ("🎉", "💰", "🔥", "✅", "📱", "🙏", "😍", "⚠️")


def _substitute(text: str, table: dict[str, str], rng: random.Random, p: float) -> str:
    """Replace characters of 4+ letter words using ``table`` with probability ``p``."""
    chars = list(text)
    eligible = [
        i for m in _WORD_RE.finditer(text) for i in range(m.start(), m.end()) if chars[i] in table
    ]
    if not eligible:
        return text
    chosen = [i for i in eligible if rng.random() < p] or [rng.choice(eligible)]
    for i in chosen:
        chars[i] = table[chars[i]]
    return "".join(chars)


def leetspeak(text: str, rng: random.Random) -> str:
    """``orange`` -> ``0r4ng3``."""
    return _substitute(text, _LEET, rng, 0.5)


def homoglyphs(text: str, rng: random.Random) -> str:
    """Latin letters replaced by identical-looking Cyrillic letters."""
    return _substitute(text, _CYRILLIC, rng, 0.5)


def _pick_words(text: str, rng: random.Random, n: int) -> list[re.Match[str]]:
    words = list(_WORD_RE.finditer(text))
    return sorted(rng.sample(words, min(n, len(words))), key=lambda m: m.start())


def _rewrite_words(text: str, matches: list[re.Match[str]], fn: Callable[[str], str]) -> str:
    out, last = [], 0
    for m in matches:
        out += [text[last : m.start()], fn(m.group(0))]
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def spaced_letters(text: str, rng: random.Random) -> str:
    """``code`` -> ``c o d e`` for two random words."""
    return _rewrite_words(text, _pick_words(text, rng, 2), " ".join)


def zero_width(text: str, rng: random.Random) -> str:
    """Invisible zero-width spaces inserted inside three words."""

    def insert(word: str) -> str:
        cut = rng.randrange(1, len(word))
        return word[:cut] + "​" + word[cut:]

    return _rewrite_words(text, _pick_words(text, rng, 3), insert)


def emojis(text: str, rng: random.Random) -> str:
    """Emojis inserted inside two words and appended at the end."""

    def insert(word: str) -> str:
        cut = rng.randrange(1, len(word))
        return word[:cut] + rng.choice(_EMOJIS) + word[cut:]

    return _rewrite_words(text, _pick_words(text, rng, 2), insert) + " " + rng.choice(_EMOJIS)


def strip_accents(text: str, rng: random.Random) -> str:
    """``Félicitations`` -> ``Felicitations``."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def upper(text: str, rng: random.Random) -> str:
    """Whole message in capital letters."""
    return text.upper()


PERTURBATIONS: dict[str, Callable[[str, random.Random], str]] = {
    "leetspeak": leetspeak,
    "homoglyphs": homoglyphs,
    "spaced_letters": spaced_letters,
    "zero_width": zero_width,
    "emojis": emojis,
    "strip_accents": strip_accents,
    "upper": upper,
}
