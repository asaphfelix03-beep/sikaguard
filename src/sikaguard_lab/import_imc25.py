"""Import real French smishing SMS from the IMC'25 dataset (CC BY 4.0).

Agarwal, Papasavva, Suarez-Tangil, Vasek (2025). *Fishing for Smishing:
Understanding SMS Phishing Infrastructure and Strategies by Mining Public User
Reports.* ACM IMC '25. https://doi.org/10.1145/3730567.3764431 —
https://github.com/reportsmishing/Smishing-Dataset-IMC25

Usage::

    python -m sikaguard_lab.import_imc25 \
        --csv data/external/imc25_final_dataset_output.csv \
        --exclude data/sources/review/imc25_exclusions.csv

The corpus is already anonymised with Presidio-style tags. They are rewritten
so that no tag exists in one class only (the model would otherwise learn
"contains <DATE_TIME> = scam"):

* ``<PHONE_NUMBER>`` → ``<TEL>``, ``<EMAIL_ADDRESS>`` → ``<EMAIL>``;
* person / brand / place / group tags → ``<NOM>`` (also frequent in real
  legitimate SMS);
* identifier-like tags (licence, bank, IBAN, parcel numbers…) → ``<REF>``;
* ``<DATE_TIME>`` → a plain date (``12/03``), drawn deterministically;
* ``<URL>`` → the shortener domain when the corpus records one
  (``bit[.]ly/…``), otherwise kept as the ``<URL>`` placeholder.

Messages flagged as legitimate by a human review (label noise of user
reports) are listed in ``data/sources/review/imc25_exclusions.csv`` and left out.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from collections.abc import Sequence
from pathlib import Path

from sikaguard.normalize import normalize
from sikaguard.pii import anonymize
from sikaguard_lab.schema import OPTIONAL_COLUMNS, RAW_COLUMNS, read_csv, validate_rows, write_csv

SOURCE_REF = "https://github.com/reportsmishing/Smishing-Dataset-IMC25"
KEPT_SCAM_TYPES = {"banking", "telecom", "delivery", "government", "others", "hey mum/dad"}

_NAME_TAGS = {"<NAMED_ENTITY>", "<PERSON>", "<LOCATION>", "<NRP>"}
_TAG_RE = re.compile(r"<[A-Z_]+>")
_COUNTRIES = {"FRA": "FR", "BEL": "BE", "CAN": "CA"}
_SCHEME_RE = re.compile(r"^(?:https?://)?", re.IGNORECASE)


def _shortener_link(shortener: str, rng: random.Random) -> str:
    host = _SCHEME_RE.sub("", shortener.strip().split()[0]).rstrip("/").replace(".", "[.]")
    path = "".join(rng.choice("abcdefghijkmnpqrstuvwxyz23456789") for _ in range(6))
    return f"{host}/{path}"


def rewrite_tags(text: str, shortener: str, rng: random.Random) -> str:
    """Rewrite the corpus' anonymisation tags into sikaguard's conventions."""

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if tag == "<PHONE_NUMBER>":
            return "<TEL>"
        if tag == "<EMAIL_ADDRESS>":
            return "<EMAIL>"
        if tag in _NAME_TAGS:
            return "<NOM>"
        if tag == "<DATE_TIME>":
            return f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}"
        if tag == "<URL>":
            return _shortener_link(shortener, rng) if shortener.strip() else "<URL>"
        return "<REF>"

    return _TAG_RE.sub(repl, text)


def category(scam_type: str, text: str) -> str:
    """Map the corpus' scam types onto sikaguard's taxonomy."""
    has_link = "<URL>" in text or "[.]" in text
    if scam_type in {"banking", "telecom"}:
        return "usurpation_operateur"
    if scam_type == "delivery":
        return "phishing_lien"
    if scam_type == "hey mum/dad":
        return "autre_arnaque"
    return "phishing_lien" if has_link else "autre_arnaque"


def operator(scam_type: str, named_entity: str) -> str:
    entity = named_entity.lower()
    if scam_type == "banking":
        return "banque"
    if "orange" in entity:
        return "orange"
    if scam_type == "telecom":
        return "autre"
    return "aucun"


def _month(value: str) -> str:
    match = re.match(r"(\d{4})-(\d{2})", value.strip())
    return f"{match.group(1)}-{match.group(2)}" if match else ""


def convert(
    rows: Sequence[dict[str, str]],
    excluded: set[str],
    seed: int = 25,
    overrides: dict[str, dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """French rows of kept scam types, rewritten, deduplicated, minus exclusions.

    ``overrides`` maps an original text to fields corrected by hand (``text``,
    ``category``, ``operateur_cible``, ``pays``).
    """
    overrides = overrides or {}
    rng = random.Random(seed)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    counts = {"french": 0, "other_scam_type": 0, "excluded_by_review": 0, "duplicates": 0}
    for row in rows:
        if row.get("language", "").strip().lower() != "french":
            continue
        counts["french"] += 1
        if row.get("scam_type", "") not in KEPT_SCAM_TYPES:
            counts["other_scam_type"] += 1
            continue
        original = " ".join(row["text"].split())
        if original in excluded:
            counts["excluded_by_review"] += 1
            continue
        fix = overrides.get(original, {})
        text = anonymize(
            fix.get("text") or rewrite_tags(original, row.get("url_shortener", ""), rng)
        )
        key = normalize(text)
        if key in seen or not text.strip():
            counts["duplicates"] += 1
            continue
        seen.add(key)
        out.append(
            {
                "text": text[:1000],
                "label": "arnaque",
                "category": fix.get("category") or category(row["scam_type"], text),
                "operateur_cible": fix.get("operateur_cible")
                or operator(row["scam_type"], row.get("named_entity", "")),
                "pays": fix.get("pays")
                or _COUNTRIES.get(row.get("original_network_country", ""), "XX"),
                "source_type": "corpus_recherche",
                "date_observee": _month(row.get("time", "")),
                "derive_de_modele": "false",
                "confiance_annotation": "moyenne",
                "campagne": "",
                "source_ref": SOURCE_REF,
            }
        )
    return out, counts


def read_overrides(path: Path) -> dict[str, dict[str, str]]:
    """Hand corrections keyed by the original (whitespace-collapsed) text."""
    if not path.is_file():
        return {}
    return {" ".join(row.pop("original").split()): row for row in read_csv(path)}


def read_exclusions(path: Path) -> set[str]:
    """Original texts (whitespace-collapsed) judged legitimate by the human review."""
    if not path.is_file():
        return set()
    return {" ".join(row["text"].split()) for row in read_csv(path)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", type=Path, default=Path("data/external/imc25_final_dataset_output.csv")
    )
    parser.add_argument(
        "--exclude", type=Path, default=Path("data/sources/review/imc25_exclusions.csv")
    )
    parser.add_argument(
        "--overrides", type=Path, default=Path("data/sources/review/imc25_overrides.csv")
    )
    parser.add_argument("--out", type=Path, default=Path("data/sources/imc25_french.csv"))
    args = parser.parse_args(argv)
    with args.csv.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    converted, counts = convert(
        rows, read_exclusions(args.exclude), overrides=read_overrides(args.overrides)
    )
    errors = validate_rows(converted)
    if errors:
        print("\n".join(errors[:20]))
        return 1
    write_csv(args.out, converted, (*RAW_COLUMNS, *OPTIONAL_COLUMNS))
    print(f"{len(converted)} real French scam SMS -> {args.out} ({counts})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
