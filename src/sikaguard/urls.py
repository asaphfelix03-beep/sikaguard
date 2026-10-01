"""Heuristic inspection of links found in SMS."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sikaguard.pii import refang

__all__ = ["BRANDS", "SHORTENERS", "SUSPICIOUS_TLDS", "UrlInfo", "inspect_url"]

SHORTENERS = frozenset(
    {
        "bit.ly", "bitly.com", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "is.gd", "ow.ly",
        "rebrand.ly", "shorturl.at", "tiny.cc", "rb.gy", "s.id", "t.ly", "v.gd", "shorte.st",
        "bl.ink", "buff.ly", "tiny.one", "urlz.fr", "lc.cx",
    }
)  # fmt: skip

SUSPICIOUS_TLDS = frozenset(
    {
        "xyz", "top", "click", "online", "site", "live", "buzz", "icu", "shop", "vip", "club",
        "link", "tk", "ga", "cf", "gq", "ml", "pw", "info", "store", "app",
    }
)  # fmt: skip

#: Brands commonly impersonated in West-African SMS scams (operators, wallets, banks).
BRANDS = (
    "orange", "mtn", "momo", "moov", "wave", "flooz", "airtel", "wizall", "freemoney",
    "djamo", "ecobank", "sgbci", "bicici", "nsia", "uba", "coris", "westernunion",
    "moneygram", "whatsapp", "facebook",
)  # fmt: skip

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)
_IP_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
_LEET = str.maketrans("013457", "oieast")


@dataclass(frozen=True)
class UrlInfo:
    """What a link reveals about itself."""

    host: str
    is_shortener: bool
    is_ip: bool
    is_punycode: bool
    suspicious_tld: bool
    brand_lookalike: bool
    homograph: bool = False  #: the link was written with look-alike (e.g. Cyrillic) letters

    @property
    def is_suspect(self) -> bool:
        """True for IP hosts, punycode, unusual TLDs, brand look-alikes or homographs."""
        return (
            self.is_ip
            or self.is_punycode
            or self.suspicious_tld
            or self.brand_lookalike
            or self.homograph
        )


def _host(url: str) -> str:
    url = _SCHEME_RE.sub("", refang(url).strip())
    host = re.split(r"[/?#]", url, maxsplit=1)[0]
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].lower().rstrip(".")
    return host.removeprefix("www.")


def inspect_url(url: str) -> UrlInfo:
    """Inspect a (possibly defanged) URL.

    A domain is a *brand look-alike* when it contains a known brand name and
    also a hyphen, a digit, or leetspeak (``orange-money-bonus.xyz``,
    ``0range.com``). Plain brand domains (``orange.ci``) are not flagged: the
    heuristic cannot know every official domain, so it only flags the typical
    impersonation patterns.
    """
    host = _host(url)
    unleet = host.translate(_LEET)
    has_brand = any(brand in unleet.replace("-", "") for brand in BRANDS)
    decorated = "-" in host or any(ch.isdigit() for ch in host) or unleet != host
    is_ip = bool(_IP_RE.fullmatch(host))
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    return UrlInfo(
        host=host,
        is_shortener=host in SHORTENERS,
        is_ip=is_ip,
        is_punycode="xn--" in host,
        suspicious_tld=tld in SUSPICIOUS_TLDS,
        brand_lookalike=has_brand and decorated and not is_ip,
    )
