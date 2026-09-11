FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /uvx /bin/
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock uv.toml ./
COPY services/core ./services/core
COPY services/worker/pyproject.toml ./services/worker/pyproject.toml
RUN uv sync --locked --package kairo-core --no-dev --no-editable
WORKDIR /app/services/core
EXPOSE 8000
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn kairo_core.main:app --host 0.0.0.0 --port 8000"]
