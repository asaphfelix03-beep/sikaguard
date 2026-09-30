"""Command-line interface: ``sikaguard "texte du SMS"``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from sikaguard import __version__
from sikaguard.analyzer import Analyzer
from sikaguard.model import ModelIntegrityError
from sikaguard.result import Result

_LABELS = {"arnaque": "ARNAQUE", "suspect": "SUSPECT", "legitime": "LÉGITIME"}
_COLORS = {"arnaque": "\033[1;31m", "suspect": "\033[1;33m", "legitime": "\033[1;32m"}
_RESET = "\033[0m"


def _use_color(stream: TextIO) -> bool:
    return stream.isatty() and "NO_COLOR" not in os.environ


def _format(result: Result, *, color: bool) -> str:
    label = _LABELS[result.verdict]
    if color:
        label = f"{_COLORS[result.verdict]}{label}{_RESET}"
    head = f"{label}  score={result.score:.2f}"
    if result.category:
        head += f"  catégorie={result.category}"
    lines = [head]
    lines += [f"  - {reason.message}" for reason in result.reasons]
    lines.append(f"  > Conseil : {result.advice}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sikaguard",
        description="Détecte les SMS d'arnaque (Mobile Money, faux gains, phishing...).",
    )
    parser.add_argument("text", nargs="?", help="texte du SMS (sinon lu sur l'entrée standard)")
    parser.add_argument("-f", "--file", help="fichier texte : un SMS par ligne")
    parser.add_argument("--json", action="store_true", help="sortie JSON (une ligne par SMS)")
    parser.add_argument("--threshold-high", type=float, default=None, help="seuil 'arnaque'")
    parser.add_argument("--threshold-low", type=float, default=None, help="seuil 'légitime'")
    parser.add_argument("--version", action="version", version=f"sikaguard {__version__}")
    return parser


def _read_inputs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[str]:
    if args.file:
        with open(args.file, encoding="utf-8") as fh:  # noqa: PTH123
            return [line.strip() for line in fh if line.strip()]
    if args.text is not None:
        return [args.text]
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return [data]
    parser.error("indiquez un texte, un fichier (-f) ou envoyez le SMS sur l'entrée standard")
    return []  # pragma: no cover - parser.error exits


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
    parser = _parser()
    args = parser.parse_args(argv)
    texts = _read_inputs(args, parser)
    try:
        analyzer = Analyzer(threshold_high=args.threshold_high, threshold_low=args.threshold_low)
    except ModelIntegrityError as exc:
        print(f"Erreur : modèle invalide ({exc})", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    if analyzer.model.manifest.not_for_production and not args.json:
        print(
            "Attention : modèle d'amorçage, ne pas utiliser en production.",
            file=sys.stderr,
        )
    try:
        results = analyzer.analyze_batch(texts)
    except ValueError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    color = _use_color(sys.stdout)
    for result in results:
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False))
        else:
            print(_format(result, color=color))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
