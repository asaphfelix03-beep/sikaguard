import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sikaguard.analyzer import MODEL_DIR_ENV
from sikaguard.cli import main

SCAM = "Envoyez votre code secret au <TEL> sinon votre compte Orange Money sera bloqué"


@pytest.fixture(autouse=True)
def _tiny_model_env(tiny_model_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_DIR_ENV, str(tiny_model_dir))


def test_cli_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([SCAM]) == 0
    captured = capsys.readouterr()
    assert "ARNAQUE" in captured.out
    assert "Conseil" in captured.out
    assert "amorçage" in captured.err


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", SCAM]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "arnaque"
    assert payload["reasons"]


def test_cli_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sms = tmp_path / "sms.txt"
    sms.write_text(f"{SCAM}\n\nJe suis arrivé à la maison\n", encoding="utf-8")
    assert main(["--json", "-f", str(sms)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["verdict"] for line in lines] == ["arnaque", "legitime"]


def test_cli_invalid_thresholds(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--threshold-high", "0.2", "--threshold-low", "0.8", SCAM]) == 2
    assert "threshold" in capsys.readouterr().err


def test_cli_empty_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["   "]) == 2
    assert "empty" in capsys.readouterr().err


def test_cli_broken_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_DIR_ENV, str(tmp_path))
    assert main([SCAM]) == 1


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "sikaguard" in capsys.readouterr().out


def test_cli_windows_console_encoding(tiny_model_dir: Path) -> None:
    env = {**os.environ, MODEL_DIR_ENV: str(tiny_model_dir), "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run(
        [sys.executable, "-m", "sikaguard.cli", "Félicitations 🎉 vous avez gagné 500000F"],
        capture_output=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("cp1252", errors="replace")
    assert b"score=" in proc.stdout


def test_cli_stdin(tiny_model_dir: Path) -> None:
    env = {**os.environ, MODEL_DIR_ENV: str(tiny_model_dir), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "sikaguard.cli", "--json"],
        input=SCAM.encode("utf-8"),
        capture_output=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["verdict"] == "arnaque"
