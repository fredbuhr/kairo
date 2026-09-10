FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58
WORKDIR /app
COPY . .
ARG KAIRO_WORKER_EXTRAS=intelligence
RUN if [ -n "$KAIRO_WORKER_EXTRAS" ]; then \
      uv pip install --system ".[${KAIRO_WORKER_EXTRAS}]"; \
    else \
      uv pip install --system .; \
    fi
CMD ["python", "-m", "kairo_worker.main"]
