FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /uvx /usr/local/bin/
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
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS runtime
COPY services/worker/runtime-packages.txt /tmp/kairo-runtime-packages.txt
RUN apt-get update && xargs -r apt-get install -y --no-install-recommends < /tmp/kairo-runtime-packages.txt \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 kairo
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
USER 10001:10001
WORKDIR /app/services/worker
CMD ["python", "-m", "kairo_worker.main"]
