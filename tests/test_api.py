import logging

import pytest
from fastapi.testclient import TestClient

from sikaguard.analyzer import Analyzer
from sikaguard.api import MAX_BATCH, MAX_TEXT_LENGTH, create_app
from sikaguard.model import LoadedModel

SCAM = "Envoyez votre code secret au <TEL> sinon votre compte Orange Money sera bloqué"
MARKER = "ZZPRIVATEMARKERZZ"


@pytest.fixture
def client(tiny_model: LoadedModel) -> TestClient:
    return TestClient(create_app(Analyzer(model=tiny_model)), raise_server_exceptions=False)


def test_analyze(client: TestClient) -> None:
    response = client.post("/v1/analyze", json={"text": SCAM})
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "arnaque"
    assert body["category"] == "usurpation_operateur"
    assert {"code", "message"} <= set(body["reasons"][0])
    assert body["model_version"] == "test"


def test_security_headers(client: TestClient) -> None:
    response = client.post("/v1/analyze", json={"text": SCAM})
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "a" * (MAX_TEXT_LENGTH + 1)},
        {"text": 42},
        {},
        {"texte": SCAM},
    ],
)
def test_analyze_validation(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/v1/analyze", json=payload).status_code == 422


def test_max_length_is_accepted(client: TestClient) -> None:
    assert client.post("/v1/analyze", json={"text": "a" * MAX_TEXT_LENGTH}).status_code == 200


def test_batch(client: TestClient) -> None:
    response = client.post("/v1/analyze/batch", json={"texts": [SCAM, "On se voit demain"]})
    assert response.status_code == 200
    assert [r["verdict"] for r in response.json()["results"]] == ["arnaque", "legitime"]


@pytest.mark.parametrize(
    "texts", [[], ["ok"] * (MAX_BATCH + 1), ["ok", " "], ["a" * (MAX_TEXT_LENGTH + 1)]]
)
def test_batch_validation(client: TestClient, texts: list[str]) -> None:
    assert client.post("/v1/analyze/batch", json={"texts": texts}).status_code == 422


def test_info_and_health(client: TestClient) -> None:
    info = client.get("/v1/info").json()
    assert info["model_version"] == "test"
    assert info["not_for_production"] is True
    assert info["api_version"]
    assert client.get("/health").json() == {"status": "ok", "model_version": "test"}


def test_sms_text_is_never_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client.post("/v1/analyze", json={"text": f"{SCAM} {MARKER}"})
    client.post("/v1/analyze/batch", json={"texts": [f"Bonjour {MARKER}"]})
    client.post("/v1/analyze", json={"text": f"   {MARKER}" + "x" * 2000})
    assert MARKER not in caplog.text
    assert "verdict=arnaque" in caplog.text


def test_internal_error_is_generic_and_not_leaked(
    tiny_model: LoadedModel, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyzer = Analyzer(model=tiny_model)

    def boom(text: str) -> None:
        raise RuntimeError(f"failure while processing {text}")

    monkeypatch.setattr(analyzer, "analyze", boom)
    client = TestClient(create_app(analyzer), raise_server_exceptions=False)
    caplog.set_level(logging.DEBUG)
    response = client.post("/v1/analyze", json={"text": MARKER})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert MARKER not in caplog.text
    assert "RuntimeError" in caplog.text


def test_openapi_schema(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/v1/analyze", "/v1/analyze/batch", "/v1/info", "/health"} <= set(paths)
