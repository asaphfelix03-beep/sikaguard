# syntax=docker/dockerfile:1
# sikaguard REST API — small, non-root image.
#   docker build -t sikaguard-api .
#   docker run --rm -p 8000:8000 sikaguard-api

FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src/sikaguard ./src/sikaguard
RUN pip install --no-cache-dir build==1.* && python -m build --wheel --outdir /dist

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 sikaguard
COPY --from=build /dist/*.whl /tmp/
RUN pip install "$(ls /tmp/*.whl)[api]" && rm /tmp/*.whl
USER sikaguard
WORKDIR /home/sikaguard
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "sikaguard.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
