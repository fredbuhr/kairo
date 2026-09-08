FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY . .
ARG KAIRO_WORKER_EXTRAS=intelligence
RUN if [ -n "$KAIRO_WORKER_EXTRAS" ]; then \
      uv pip install --system ".[${KAIRO_WORKER_EXTRAS}]"; \
    else \
      uv pip install --system .; \
    fi
CMD ["python", "-m", "kairo_worker.main"]
