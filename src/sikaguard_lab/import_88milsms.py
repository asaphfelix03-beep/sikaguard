"""Import real legitimate SMS from the 88milSMS corpus (CC BY 4.0).

88milSMS: more than 88,000 authentic French SMS collected in 2011 in the
Montpellier area and anonymised by the sud4science / CoMeRe projects
(Panckhurst et al., 2014; https://hdl.handle.net/11403/comere/cmr-88milsms).

Usage::

    python -m sikaguard_lab.import_88milsms \
        --xml data/external/cmr-88milsms-tei-v1.xml --n-train 150 --n-eval 1000

Writes two **disjoint** random samples:

* ``data/sources/88milsms_sample.csv`` — training material (legitimate, ``personnel``);
* ``data/eval/88milsms_eval.csv`` — never used for training: an external
  benchmark of the false-positive rate on real messages.
"""

from __future__ import annotations

import argparse
import random
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from pathlib import Path

from sikaguard.normalize import normalize
from sikaguard.pii import anonymize, find_urls, has_phone_number
from sikaguard_lab.schema import OPTIONAL_COLUMNS, RAW_COLUMNS, read_csv, validate_rows, write_csv

SOURCE_REF = "https://hdl.handle.net/11403/comere/cmr-88milsms"
PLACEHOLDERS = {
    "[_forename_]": "<NOM>",
    "[_surname_]": "<NOM>",
    "[_nickname_]": "<NOM>",
    "[_tel_]": "<TEL>",
}
MIN_LEN, MAX_LEN = 15, 600

# Chain letters ("send this to 10 friends") are a scam pattern in our taxonomy:
# they must not enter the corpus as "legitimate".
_CHAIN_LETTER_RE = re.compile(
    r"(envoie|envoyez|transf[eè]re|fais (?:passer|tourner)|partage).{0,60}"
    r"(ce (?:message|sms|texto)|à \d+ (?:personnes|amis|contacts))",
    re.IGNORECASE,
)


class _RejectedTagError(Exception):
    """The post contains an anonymisation tag we do not map (address, brand...)."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _render(element: ET.Element) -> str:
    parts = [element.text or ""]
    for child in element:
        if _local(child.tag) == "fs" and child.get("type") == "anonymisation":
            strings = [s.text or "" for s in child.iter() if _local(s.tag) == "string"]
            tag = strings[0] if strings else ""
            if tag not in PLACEHOLDERS:
                raise _RejectedTagError(tag)
            parts.append(PLACEHOLDERS[tag])
        else:
            parts.append(_render(child))
        parts.append(child.tail or "")
    return "".join(parts)


def iter_posts(xml_path: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(text, yyyy-mm)`` for every usable SMS of the corpus."""
    for _, element in ET.iterparse(xml_path, events=("end",)):  # noqa: S314 - see import note
        if _local(element.tag) != "post" or element.get("type") != "sms":
            continue
        try:
            text = " ".join(_render(p) for p in element.iter() if _local(p.tag) == "p")
        except _RejectedTagError:
            element.clear()
            continue
        when = (element.get("when-iso") or "")[:7]
        element.clear()
        text = " ".join(text.split())
        if MIN_LEN <= len(text) <= MAX_LEN:
            yield text, when


def _keep(text: str) -> bool:
    return not (_CHAIN_LETTER_RE.search(text) or find_urls(text) or has_phone_number(text))


def _row(text: str, when: str) -> dict[str, str]:
    return {
        "text": anonymize(text),
        "label": "legitime",
        "category": "personnel",
        "operateur_cible": "aucun",
        "pays": "FR",
        "source_type": "corpus_recherche",
        "date_observee": when,
        "derive_de_modele": "false",
        "confiance_annotation": "haute",
        "campagne": "",
        "source_ref": SOURCE_REF,
    }


def sample(
    xml_path: Path,
    n_train: int,
    n_eval: int,
    seed: int = 2011,
    exclude: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Two disjoint random samples (deduplicated on the normalized text).

    ``exclude`` holds normalized texts that must not be drawn (e.g. an existing
    held-out benchmark that has to stay unchanged).
    """
    exclude = exclude or set()
    seen: set[str] = set()
    pool: list[tuple[str, str]] = []
    for text, when in iter_posts(xml_path):
        key = normalize(text)
        if key in seen or not _keep(text) or normalize(anonymize(text)) in exclude:
            continue
        seen.add(key)
        pool.append((text, when))
    if len(pool) < n_train + n_eval:
        raise ValueError(f"only {len(pool)} usable SMS, {n_train + n_eval} requested")
    chosen = random.Random(seed).sample(pool, n_train + n_eval)
    rows = [_row(t, w) for t, w in chosen]
    return rows[:n_train], rows[n_train:]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, default=Path("data/external/cmr-88milsms-tei-v1.xml"))
    parser.add_argument("--n-train", type=int, default=150)
    parser.add_argument("--n-eval", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2011)
    parser.add_argument("--train-out", type=Path, default=Path("data/sources/88milsms_sample.csv"))
    parser.add_argument("--eval-out", type=Path, default=Path("data/eval/88milsms_eval.csv"))
    parser.add_argument(
        "--exclude",
        type=Path,
        action="append",
        default=[],
        help="CSV whose texts must not be drawn (repeatable); use it to keep a benchmark fixed",
    )
    args = parser.parse_args(argv)
    exclude = {normalize(row["text"]) for path in args.exclude for row in read_csv(path)}
    train, held_out = sample(args.xml, args.n_train, args.n_eval, args.seed, exclude)
    for rows in (train, held_out):
        errors = validate_rows(rows) if rows else []
        if errors:  # pragma: no cover - anonymize() + filters make this unreachable
            raise ValueError("\n".join(errors[:10]))
    columns = (*RAW_COLUMNS, *OPTIONAL_COLUMNS)
    write_csv(args.train_out, train, columns)
    print(f"{len(train)} training SMS -> {args.train_out}")
    if args.n_eval:
        write_csv(args.eval_out, held_out, columns)
        print(f"{len(held_out)} held-out SMS -> {args.eval_out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
