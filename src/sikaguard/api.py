"""REST API (optional extra: ``pip install "sikaguard[api]"``).

Run::

    uvicorn sikaguard.api:app --host 0.0.0.0 --port 8000

Privacy by design: the text of the SMS is never logged nor stored. Logs only
contain the text length, the verdict and the latency.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel, Field

from sikaguard import __version__
from sikaguard.analyzer import Analyzer, get_default_analyzer
from sikaguard.result import Result

__all__ = ["MAX_BATCH", "MAX_TEXT_LENGTH", "app", "create_app"]

MAX_TEXT_LENGTH = 1000
MAX_BATCH = 100

# A child of uvicorn's error logger: under uvicorn the lines use its handler and
# level (visible by default); elsewhere they propagate to the root logger as usual.
logger = logging.getLogger("uvicorn.error.sikaguard")


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("text must not be blank")
    return value


SmsText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_TEXT_LENGTH, examples=["Envoyez votre code secret au ..."]),
    AfterValidator(_not_blank),
]


class AnalyzeRequest(BaseModel):
    text: SmsText


class BatchRequest(BaseModel):
    texts: Annotated[list[SmsText], Field(min_length=1, max_length=MAX_BATCH)]


class ReasonOut(BaseModel):
    code: str
    message: str


class AnalyzeResponse(BaseModel):
    verdict: Literal["arnaque", "suspect", "legitime"]
    score: float
    category: str | None
    category_score: float | None
    reasons: list[ReasonOut]
    advice: str
    model_version: str


class BatchResponse(BaseModel):
    results: list[AnalyzeResponse]


class InfoResponse(BaseModel):
    api_version: str
    model_version: str
    dataset_version: str
    sklearn_version: str
    threshold_high: float
    threshold_low: float
    categories: list[str]
    not_for_production: bool
    training_data: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_version: str


def _to_response(result: Result) -> AnalyzeResponse:
    return AnalyzeResponse.model_validate(result.to_dict())


def create_app(analyzer: Analyzer | None = None) -> FastAPI:
    """Build the FastAPI application. ``analyzer`` defaults to the bundled model."""
    app = FastAPI(
        title="sikaguard",
        version=__version__,
        description=(
            "Explainable detection of French-language SMS and Mobile Money scams. "
            "The SMS text is never logged nor stored."
        ),
    )

    def get_analyzer() -> Analyzer:
        return analyzer if analyzer is not None else get_default_analyzer()

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        # Only the exception type is logged: messages could contain user data.
        logger.error("unhandled error on %s: %s", request.url.path, type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.post("/v1/analyze", response_model=AnalyzeResponse, tags=["analysis"])
    def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
        """Analyze one SMS."""
        start = time.perf_counter()
        result = get_analyzer().analyze(body.text)
        logger.info(
            "analyze length=%d verdict=%s latency_ms=%.1f",
            len(body.text),
            result.verdict,
            1000 * (time.perf_counter() - start),
        )
        return _to_response(result)

    @app.post("/v1/analyze/batch", response_model=BatchResponse, tags=["analysis"])
    def analyze_batch(body: BatchRequest) -> BatchResponse:
        """Analyze up to 100 SMS."""
        start = time.perf_counter()
        results = get_analyzer().analyze_batch(body.texts)
        logger.info(
            "analyze_batch size=%d scams=%d latency_ms=%.1f",
            len(results),
            sum(r.verdict == "arnaque" for r in results),
            1000 * (time.perf_counter() - start),
        )
        return BatchResponse(results=[_to_response(r) for r in results])

    @app.get("/v1/info", response_model=InfoResponse, tags=["service"])
    def info() -> dict[str, Any]:
        """Model and dataset versions, decision thresholds."""
        return {"api_version": __version__, **get_analyzer().info()}

    @app.get("/health", response_model=HealthResponse, tags=["service"])
    def health() -> dict[str, str]:
        """Liveness and readiness probe (loads the model on first call)."""
        return {"status": "ok", "model_version": get_analyzer().model.manifest.model_version}

    return app


app = create_app()
