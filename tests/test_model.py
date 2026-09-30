import json
import shutil
from pathlib import Path

import pytest

from sikaguard import model as model_module
from sikaguard.model import (
    MANIFEST_FILE,
    MODEL_FILE,
    LoadedModel,
    Manifest,
    ModelIntegrityError,
    load_model,
    sha256_file,
)


@pytest.fixture
def model_copy(tiny_model_dir: Path, tmp_path: Path) -> Path:
    target = tmp_path / "model"
    shutil.copytree(tiny_model_dir, target)
    return target


def test_round_trip(tiny_model: LoadedModel) -> None:
    assert tiny_model.manifest.model_version == "test"
    assert tiny_model.manifest.not_for_production
    assert set(tiny_model.manifest.categories) == {
        "usurpation_operateur",
        "faux_gain",
        "faux_transfert",
    }
    assert tiny_model.binary.predict_proba(["Envoyez votre code secret"]).shape == (1, 2)


def test_manifest_hash_matches_file(tiny_model_dir: Path, tiny_model: LoadedModel) -> None:
    assert tiny_model.manifest.sha256 == sha256_file(tiny_model_dir / MODEL_FILE)


def test_tampered_model_is_rejected(model_copy: Path) -> None:
    path = model_copy / MODEL_FILE
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(ModelIntegrityError, match="SHA-256"):
        load_model(model_copy)


def test_missing_model_file(model_copy: Path) -> None:
    (model_copy / MODEL_FILE).unlink()
    with pytest.raises(ModelIntegrityError, match="Model file not found"):
        load_model(model_copy)


def test_missing_manifest(model_copy: Path) -> None:
    (model_copy / MANIFEST_FILE).unlink()
    with pytest.raises(ModelIntegrityError, match="Manifest not found"):
        load_model(model_copy)


def test_invalid_manifest_json(model_copy: Path) -> None:
    (model_copy / MANIFEST_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(ModelIntegrityError, match="Invalid manifest JSON"):
        load_model(model_copy)


def test_manifest_not_an_object(model_copy: Path) -> None:
    (model_copy / MANIFEST_FILE).write_text("[]", encoding="utf-8")
    with pytest.raises(ModelIntegrityError, match="expected a JSON object"):
        load_model(model_copy)


def test_manifest_missing_key(model_copy: Path) -> None:
    path = model_copy / MANIFEST_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["sha256"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ModelIntegrityError, match="Invalid manifest"):
        load_model(model_copy)


def test_manifest_bad_thresholds(model_copy: Path) -> None:
    path = model_copy / MANIFEST_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data["threshold_low"], data["threshold_high"] = 0.9, 0.2
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ModelIntegrityError, match="thresholds"):
        load_model(model_copy)


def test_untrusted_type_is_rejected(model_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_module, "ALLOWED_TYPES", frozenset())
    with pytest.raises(ModelIntegrityError, match="untrusted types"):
        load_model(model_copy)


def test_unreadable_model_with_matching_hash(model_copy: Path) -> None:
    path = model_copy / MODEL_FILE
    path.write_bytes(b"this is not a zip file")
    manifest_path = model_copy / MANIFEST_FILE
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["sha256"] = sha256_file(path)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ModelIntegrityError, match="Unreadable model file"):
        load_model(model_copy)


def test_sklearn_version_mismatch_warns(model_copy: Path) -> None:
    path = model_copy / MANIFEST_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sklearn_version"] = "0.0.1"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.warns(UserWarning, match="scikit-learn 0.0.1"):
        load_model(model_copy)


def test_manifest_round_trip(tiny_model: LoadedModel) -> None:
    assert Manifest.from_dict(tiny_model.manifest.to_dict()) == tiny_model.manifest
