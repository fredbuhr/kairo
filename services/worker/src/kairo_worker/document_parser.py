from __future__ import annotations

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


def _chunk_text(text: str, *, max_chars: int = 4000) -> list[dict[str, Any]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append({"text": "\n\n".join(current), "metadata": {"kind": "text"}})
                current = []
                current_len = 0
            for offset in range(0, len(paragraph), max_chars):
                piece = paragraph[offset : offset + max_chars].strip()
                if piece:
                    chunks.append({"text": piece, "metadata": {"kind": "text", "split": True}})
            continue
        extra = len(paragraph) + (2 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append({"text": "\n\n".join(current), "metadata": {"kind": "text"}})
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += extra
    if current:
        chunks.append({"text": "\n\n".join(current), "metadata": {"kind": "text"}})
    return chunks


def _plain_text_fallback(content: bytes, media_type: str | None) -> tuple[str, str, str | None, dict[str, Any]]:
    allowed = {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/json",
        "text/csv",
        "text/html",
    }
    if (media_type or "").split(";", 1)[0].lower() not in allowed:
        raise ValueError("Docling is unavailable and this media type has no deterministic fallback parser")
    return content.decode("utf-8", errors="replace"), "text-fallback", None, {"docling_available": False}


def _parse_with_docling(path: Path) -> tuple[str, str, str | None, dict[str, Any]]:
    from docling.document_converter import DocumentConverter

    # Converter and any models live only in this bounded child process, never on the async loop.
    result = DocumentConverter().convert(path)
    text = result.document.export_to_markdown()
    try:
        version = importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        version = None
    return text, "docling", version, {"docling_available": True, "export": "markdown"}


def parse_document(path: Path, media_type: str, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("docling") is not None:
        text, parser, version, metadata = _parse_with_docling(path)
    else:
        text, parser, version, metadata = _plain_text_fallback(path.read_bytes(), media_type)
    if len(text) > max_chars:
        raise ValueError(f"Document text exceeds configured {max_chars} character limit")
    chunks = _chunk_text(text)
    if not chunks:
        raise ValueError("Document parser produced no textual chunks")
    return {"parser": parser, "parser_version": version, "metadata": metadata, "chunks": chunks}


def main() -> None:
    source, destination, media_type, max_chars = sys.argv[1:]
    try:
        result = parse_document(Path(source), media_type, int(max_chars))
    except ValueError as exc:
        result = {"error": str(exc), "retryable": False}
    except Exception as exc:
        # Preserve a useful failure class without echoing source contents or provider credentials.
        result = {"error": f"Document parser failed ({type(exc).__name__})", "retryable": True}
    Path(destination).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
