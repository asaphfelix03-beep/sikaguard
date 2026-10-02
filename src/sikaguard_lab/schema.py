"""Dataset schema and validation."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from sikaguard.pii import has_phone_number, url_spans
from sikaguard.result import LEGIT_CATEGORIES, SCAM_CATEGORIES

LABELS = ("arnaque", "legitime")
CATEGORIES_BY_LABEL = {"arnaque": SCAM_CATEGORIES, "legitime": LEGIT_CATEGORIES}
OPERATORS = ("orange", "mtn", "moov", "wave", "banque", "autre", "aucun")
COUNTRIES = ("CI", "SN", "BF", "ML", "BJ", "TG", "CM", "NE", "GN", "FR", "BE", "CA", "XX")
#: Countries where sikaguard is meant to be used in production.
WEST_AFRICA = frozenset({"CI", "SN", "BF", "ML", "BJ", "TG", "CM", "NE", "GN"})
SOURCE_TYPES = (
    "operateur",
    "autorite",
    "presse",
    "reseau_social",
    "corpus_recherche",
    "depot_open_source",
    "amorcage",
)
CONFIDENCE = ("haute", "moyenne")
BOOLEANS = ("true", "false")
SPLITS = ("train", "test")
MAX_TEXT_LEN = 1000

RAW_COLUMNS = (
    "text",
    "label",
    "category",
    "operateur_cible",
    "pays",
    "source_type",
    "date_observee",
    "derive_de_modele",
    "confiance_annotation",
)
#: Optional raw columns (empty when absent):
#: ``campagne``  — id of a documented scam campaign; all its rows share one group,
#:                 so a campaign is never split between train and test;
#: ``source_ref`` — public URL of an official or press source (never for social media).
OPTIONAL_COLUMNS = ("campagne", "source_ref")
COLUMNS = ("id", *RAW_COLUMNS, *OPTIONAL_COLUMNS, "group_id", "split")

_DATE_RE = re.compile(r"(?:\d{4}-(?:0[1-9]|1[0-2]))?")
_CAMPAIGN_RE = re.compile(r"[a-z0-9_-]*")
_SOURCE_REF_RE = re.compile(r"(?:https?://\S+)?")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into a list of dicts (all values are strings)."""
    with path.open(encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], columns: Sequence[str]) -> None:
    """Write rows to a UTF-8 CSV with LF line endings and a fixed column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


_LIVE_SCHEME_RE = re.compile(r"https?://", re.IGNORECASE)
_ANY_SCHEME_RE = re.compile(r"^h[tx]{2}ps?(?::|\[:\])//", re.IGNORECASE)


def _url_not_defanged(text: str) -> bool:
    """True if a link could still be clicked: a live scheme or a live dot in its host.

    Dots in the path (``app.apk``) are harmless once the host is defanged, and
    truncated fragments such as ``hxxps://orange`` carry nothing to defang.
    """
    for start, end in url_spans(text):
        span = text[start:end]
        host = re.split(r"[/?#]", _ANY_SCHEME_RE.sub("", span), maxsplit=1)[0]
        if _LIVE_SCHEME_RE.search(span) or "." in host.replace("[.]", ""):
            return True
    return False


def _check_row(row: Mapping[str, str], line: int, processed: bool) -> list[str]:
    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(f"ligne {line}: {msg}")

    text = row.get("text", "")
    label = row.get("label", "")
    if not text.strip():
        err("texte vide")
    if len(text) > MAX_TEXT_LEN:
        err(f"texte trop long ({len(text)} > {MAX_TEXT_LEN})")
    if has_phone_number(text):
        err("numéro de téléphone non masqué (utiliser <TEL>)")
    if _EMAIL_RE.search(text):
        err("adresse e-mail non masquée (utiliser <EMAIL>)")
    if _url_not_defanged(text):
        err("lien non désamorcé (utiliser hxxp:// et [.])")
    if label not in LABELS:
        err(f"label invalide: {label!r}")
    elif row.get("category") not in CATEGORIES_BY_LABEL[label]:
        err(f"catégorie {row.get('category')!r} incompatible avec le label {label!r}")
    checks = (
        ("operateur_cible", OPERATORS),
        ("pays", COUNTRIES),
        ("source_type", SOURCE_TYPES),
        ("derive_de_modele", BOOLEANS),
        ("confiance_annotation", CONFIDENCE),
    )
    for column, allowed in checks:
        if row.get(column) not in allowed:
            err(f"{column} invalide: {row.get(column)!r}")
    if not _DATE_RE.fullmatch(row.get("date_observee", "")):
        err(f"date_observee invalide: {row.get('date_observee')!r} (attendu AAAA-MM ou vide)")
    if not _CAMPAIGN_RE.fullmatch(row.get("campagne") or ""):
        err(f"campagne invalide: {row.get('campagne')!r} (minuscules, chiffres, - et _)")
    source_ref = row.get("source_ref") or ""
    if not _SOURCE_REF_RE.fullmatch(source_ref):
        err(f"source_ref invalide: {source_ref!r} (URL http(s) ou vide)")
    elif source_ref and row.get("source_type") == "reseau_social":
        err("source_ref interdit pour un réseau social (provenance privée, voir data/raw)")
    if processed:
        if row.get("split") not in SPLITS:
            err(f"split invalide: {row.get('split')!r}")
        if not row.get("group_id", "").isdigit():
            err(f"group_id invalide: {row.get('group_id')!r}")
    return errors


def validate_rows(rows: Sequence[Mapping[str, str]], *, processed: bool = False) -> list[str]:
    """Return human-readable validation errors (empty list when the data is valid).

    Line numbers refer to the CSV file (the header is line 1).
    """
    expected = COLUMNS if processed else RAW_COLUMNS
    if not rows:
        return ["aucune ligne"]
    missing = [c for c in expected if c not in rows[0]]
    if missing:
        return [f"colonnes manquantes: {missing}"]
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):
        errors.extend(_check_row(row, i, processed))
    if processed:
        ids = [row["id"] for row in rows]
        if len(set(ids)) != len(ids):
            errors.append("identifiants dupliqués")
    return errors
