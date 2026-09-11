FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock uv.toml ./
COPY services/core/pyproject.toml ./services/core/pyproject.toml
COPY services/worker ./services/worker
ARG KAIRO_WORKER_EXTRAS=intelligence
RUN if [ -n "$KAIRO_WORKER_EXTRAS" ]; then \
      uv sync --locked --package kairo-worker --no-dev --no-editable --extra "$KAIRO_WORKER_EXTRAS"; \
    else \
      uv sync --locked --package kairo-worker --no-dev --no-editable; \
    fi
WORKDIR /app/services/worker
CMD ["python", "-m", "kairo_worker.main"]
