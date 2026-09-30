"""Secure persistence of the models.

The model is serialized with `skops <https://skops.readthedocs.io>`_, never with
``pickle``: loading a pickle can execute arbitrary code. Before loading, the
file's SHA-256 is checked against ``manifest.json`` and the only non-standard
types accepted are listed in :data:`ALLOWED_TYPES`.
"""

from __future__ import annotations

import hashlib
import json
import warnings
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sklearn
import skops
import skops.io as sio
from sklearn.pipeline import Pipeline

__all__ = [
    "ALLOWED_TYPES",
    "DEFAULT_MODEL_DIR",
    "LoadedModel",
    "Manifest",
    "ModelIntegrityError",
    "load_model",
    "save_model",
    "sha256_file",
]

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "assets"
MODEL_FILE = "model.skops"
MANIFEST_FILE = "manifest.json"

#: Custom types the loader is allowed to instantiate (everything else skops
#: considers untrusted makes loading fail).
ALLOWED_TYPES: frozenset[str] = frozenset(
    {"sikaguard.features.SignalTransformer", "sikaguard.features.TextNormalizer"}
)


class ModelIntegrityError(RuntimeError):
    """The model files are missing, altered or contain untrusted types."""


@dataclass(frozen=True)
class Manifest:
    """Metadata written next to the model file."""

    model_version: str
    dataset_version: str
    sklearn_version: str
    skops_version: str
    threshold_high: float
    threshold_low: float
    sha256: str
    categories: tuple[str, ...]
    created_at: str
    not_for_production: bool
    training_data: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["categories"] = list(self.categories)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        try:
            manifest = cls(
                model_version=str(data["model_version"]),
                dataset_version=str(data["dataset_version"]),
                sklearn_version=str(data["sklearn_version"]),
                skops_version=str(data["skops_version"]),
                threshold_high=float(data["threshold_high"]),
                threshold_low=float(data["threshold_low"]),
                sha256=str(data["sha256"]),
                categories=tuple(str(c) for c in data["categories"]),
                created_at=str(data["created_at"]),
                not_for_production=bool(data["not_for_production"]),
                training_data=str(data["training_data"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelIntegrityError(f"Invalid manifest: {exc!r}") from exc
        if not 0.0 <= manifest.threshold_low <= manifest.threshold_high <= 1.0:
            raise ModelIntegrityError(
                "Invalid manifest: thresholds must satisfy 0 <= low <= high <= 1"
            )
        return manifest


@dataclass(frozen=True)
class LoadedModel:
    """The two-stage model and its manifest."""

    binary: Pipeline
    category: Pipeline
    manifest: Manifest


def sha256_file(path: Path) -> str:
    """Hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_model(
    binary: Pipeline,
    category: Pipeline,
    directory: Path,
    *,
    model_version: str,
    dataset_version: str,
    threshold_high: float,
    threshold_low: float,
    not_for_production: bool,
    training_data: str,
) -> Manifest:
    """Serialize both pipelines with skops and write ``manifest.json``."""
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_FILE
    sio.dump(
        {"binary": binary, "category": category},
        model_path,
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    )
    manifest = Manifest(
        model_version=model_version,
        dataset_version=dataset_version,
        sklearn_version=sklearn.__version__,
        skops_version=skops.__version__,
        threshold_high=float(threshold_high),
        threshold_low=float(threshold_low),
        sha256=sha256_file(model_path),
        categories=tuple(str(c) for c in category.classes_),
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        not_for_production=not_for_production,
        training_data=training_data,
    )
    (directory / MANIFEST_FILE).write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def load_model(directory: Path | None = None) -> LoadedModel:
    """Load and verify the model stored in ``directory`` (default: bundled model).

    Raises:
        ModelIntegrityError: missing file, invalid manifest, SHA-256 mismatch,
            untrusted type, or unexpected content.
    """
    directory = directory or DEFAULT_MODEL_DIR
    manifest_path = directory / MANIFEST_FILE
    model_path = directory / MODEL_FILE
    if not manifest_path.is_file():
        raise ModelIntegrityError(f"Manifest not found: {manifest_path}")
    if not model_path.is_file():
        raise ModelIntegrityError(f"Model file not found: {model_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelIntegrityError(f"Invalid manifest JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ModelIntegrityError("Invalid manifest: expected a JSON object")
    manifest = Manifest.from_dict(raw)

    actual = sha256_file(model_path)
    if actual != manifest.sha256:
        raise ModelIntegrityError(
            f"SHA-256 mismatch for {model_path.name}: expected {manifest.sha256}, got {actual}. "
            "The model file was altered or corrupted."
        )
    try:
        untrusted = set(sio.get_untrusted_types(file=model_path))
    except Exception as exc:
        raise ModelIntegrityError(f"Unreadable model file: {exc}") from exc
    unexpected = untrusted - ALLOWED_TYPES
    if unexpected:
        raise ModelIntegrityError(f"Model contains untrusted types: {sorted(unexpected)}")

    if manifest.sklearn_version != sklearn.__version__:
        warnings.warn(
            f"Model trained with scikit-learn {manifest.sklearn_version}, running "
            f"{sklearn.__version__}. Predictions may differ slightly.",
            UserWarning,
            stacklevel=2,
        )
    obj = sio.load(model_path, trusted=sorted(untrusted))
    if not (isinstance(obj, dict) and {"binary", "category"} <= obj.keys()):
        raise ModelIntegrityError("Unexpected model content: expected 'binary' and 'category'")
    return LoadedModel(binary=obj["binary"], category=obj["category"], manifest=manifest)
