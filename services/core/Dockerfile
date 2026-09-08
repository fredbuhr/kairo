FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY . .
RUN uv pip install --system .
EXPOSE 8000
CMD ["uvicorn", "kairo_core.main:app", "--host", "0.0.0.0", "--port", "8000"]
