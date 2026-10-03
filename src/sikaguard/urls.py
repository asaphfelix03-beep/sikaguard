"""Heuristic inspection of links found in SMS."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sikaguard.pii import refang

__all__ = ["BRANDS", "FREE_HOSTS", "SHORTENERS", "SUSPICIOUS_TLDS", "UrlInfo", "inspect_url"]

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

#: Free hosting, website builders and tunnels: anyone can publish a page under these
#: domains in minutes, which no operator or bank does for its official pages.
FREE_HOSTS = (
    "000webhostapp.com", "blogspot.com", "carrd.co", "cloudaccess.host", "duckdns.org",
    "firebaseapp.com", "github.io", "glitch.me", "godaddysites.com", "herokuapp.com",
    "netlify.app", "ngrok-free.app", "ngrok.io", "onrender.com", "pages.dev", "repl.co",
    "replit.app", "sites.google.com", "square.site", "vercel.app", "web.app", "webflow.io",
    "weebly.com", "wixsite.com", "workers.dev",
)  # fmt: skip

#: Second-level labels under which domains are registered (``orange.co.ci``).
_SECOND_LEVEL = frozenset({"ac", "co", "com", "edu", "gouv", "gov", "net", "or", "org"})
#: Brands short enough to appear inside ordinary words (``dubai``, ``mountain``) are only
#: matched in the registered domain, never in a subdomain.
_MIN_SUBDOMAIN_BRAND = 4

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
    free_hosting: bool = False  #: the page is on a free host or a website builder

    @property
    def is_suspect(self) -> bool:
        """True for IP hosts, punycode, unusual TLDs, brand look-alikes, homographs or
        free hosting."""
        return (
            self.is_ip
            or self.is_punycode
            or self.suspicious_tld
            or self.brand_lookalike
            or self.homograph
            or self.free_hosting
        )


def _host(url: str) -> str:
    url = _SCHEME_RE.sub("", refang(url).strip())
    host = re.split(r"[/?#]", url, maxsplit=1)[0]
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].lower().rstrip(".")
    return host.removeprefix("www.")


def _split_host(host: str) -> tuple[str, str]:
    """Split ``host`` into (subdomain, registered domain): ``a.b.orange.co.ci`` →
    (``a.b``, ``orange.co.ci``)."""
    labels = host.split(".")
    size = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL else 2
    return ".".join(labels[:-size]), ".".join(labels[-size:])


def _on_free_host(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in FREE_HOSTS)


def inspect_url(url: str) -> UrlInfo:
    """Inspect a (possibly defanged) URL.

    A domain is a *brand look-alike* when a known brand name appears

    * in the registered domain together with a hyphen, a digit or leetspeak
      (``orange-money-bonus.xyz``, ``0range.com``);
    * in a subdomain of a domain that is not the brand's (``flashwave.cloudaccess.host``,
      ``orange.ci.secure-login.com``);
    * anywhere in a page on a free host (``orange-money.github.io``).

    Plain brand domains (``orange.ci``, ``maxit.orange.ci``) are not flagged: the
    heuristic cannot know every official domain, so it only flags the typical
    impersonation patterns.
    """
    host = _host(url)
    unleet = host.translate(_LEET)
    subdomain, registered = _split_host(unleet)
    free_hosting = _on_free_host(host)
    has_brand = any(brand in unleet.replace("-", "") for brand in BRANDS)
    brand_in_subdomain = any(
        brand in subdomain.replace("-", "")
        for brand in BRANDS
        if len(brand) >= _MIN_SUBDOMAIN_BRAND and brand not in registered.replace("-", "")
    )
    decorated = "-" in host or any(ch.isdigit() for ch in host) or unleet != host
    is_ip = bool(_IP_RE.fullmatch(host))
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    return UrlInfo(
        host=host,
        is_shortener=host in SHORTENERS,
        is_ip=is_ip,
        is_punycode="xn--" in host,
        suspicious_tld=tld in SUSPICIOUS_TLDS,
        brand_lookalike=not is_ip
        and ((has_brand and (decorated or free_hosting)) or brand_in_subdomain),
        free_hosting=free_hosting,
    )
