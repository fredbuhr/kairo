#!/usr/bin/env python3
"""Resume bounded memory rebuild pages using a durable local request checkpoint.

The checkpoint contains no token or message content. Only run against the intended Core.
"""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def save(path: Path, state: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if os.name == "posix":
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", default="http://127.0.0.1:8000")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--limit", type=int, choices=range(1, 101), default=100, metavar="1..100")
    parser.add_argument("--message-id", action="append", default=None)
    args = parser.parse_args()
    token = os.environ.get("NEVOLIUM_OPERATIONS_TOKEN")
    if not token:
        parser.error("NEVOLIUM_OPERATIONS_TOKEN must be set (development: use the development internal token)")
    core = args.core.rstrip("/")
    if args.checkpoint.exists():
        state = json.loads(args.checkpoint.read_text(encoding="utf-8"))
        if state["core"] != core:
            parser.error("Checkpoint belongs to another Core URL")
        if args.message_id is not None or args.limit != 100:
            parser.error("Resume uses the saved selection and limit; omit --message-id and --limit")
    else:
        message_ids = [str(uuid.UUID(value)) for value in args.message_id] if args.message_id is not None else None
        if message_ids is not None and len(message_ids) > 200:
            parser.error("At most 200 selected messages; omit selection to rebuild all through a fixed watermark")
        state = {"core": core, "complete": False, "queued": 0,
                 "request": {"request_id": str(uuid.uuid4()), "message_ids": message_ids, "limit": args.limit}}
        save(args.checkpoint, state)  # Persist identity BEFORE the first possibly ambiguous request.
    retries = 0
    while not state["complete"]:
        request = urllib.request.Request(core + "/internal/v1/memory/rebuild", method="POST",
            headers={"Content-Type": "application/json", "X-Nevolium-Internal-Token": token},
            data=json.dumps(state["request"]).encode())
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                page = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 502, 503, 504} or retries >= 12:
                raise SystemExit(f"Core returned HTTP {exc.code}; checkpoint preserved for diagnosis") from None
            retries += 1
            time.sleep(5)
            continue
        except (urllib.error.URLError, TimeoutError):
            raise SystemExit("Core connection interrupted; rerun the same command to replay the saved page") from None
        retries = 0
        state["queued"] += page["queued"]
        state["complete"] = page["complete"]
        if not page["complete"]:
            state["request"].update(cursor=page["next_cursor"], through=page["through"])
        save(args.checkpoint, state)
        print(f"Queued {state['queued']} projections; complete={state['complete']}", flush=True)


if __name__ == "__main__":
    main()
