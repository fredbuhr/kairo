FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /uvx /usr/local/bin/
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock uv.toml ./
COPY services/core ./services/core
COPY services/worker/pyproject.toml ./services/worker/pyproject.toml
RUN uv sync --locked --package nevolium-core --no-dev --no-editable
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS runtime
RUN useradd --create-home --uid 10001 nevolium
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/services/core/migrations /app/services/core/migrations
COPY --from=build /app/services/core/alembic.ini /app/services/core/alembic.ini
USER 10001:10001
WORKDIR /app/services/core
EXPOSE 8000
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn nevolium_core.main:app --host 0.0.0.0 --port 8000"]
