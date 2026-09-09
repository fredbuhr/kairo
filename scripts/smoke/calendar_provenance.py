#!/usr/bin/env python3
"""Proof for provenance-preserving external calendar snapshots."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CORE = "http://localhost:8000"
INTERNAL = {"X-Kairo-Internal-Token": "CHANGE_ME_INTERNAL_TOKEN"}
OWNER = "development-user"


def json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {**(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        CORE + path,
        data=data,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode("utf-8"))
    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {body}")
    return status, body


def wait_ready() -> None:
    deadline = time.time() + 90
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _, body = json_request("GET", "/health/ready")
            if body["status"] == "ready":
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"KAIRO Core did not become ready: {last_error}")


def snapshot(events: list[dict[str, Any]], *, account_ref: str = "fixture-account") -> dict[str, Any]:
    return {
        "owner_subject": OWNER,
        "source": {
            "key": "fixture.google-calendar",
            "provider": "google",
            "external_account_ref": account_ref,
            "display_name": "Google Calendar Fixture",
            "status": "connected",
            "metadata": {"calendar_id": "primary", "fixture": True},
        },
        "events": events,
        "replace_missing": True,
    }


def event(
    external_id: str,
    title: str,
    start_at: str,
    end_at: str,
    *,
    all_day: bool = False,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "title": title,
        "start_at": start_at,
        "end_at": end_at,
        "all_day": all_day,
        "status": "confirmed",
        "location": "Fixture room",
        "source_url": f"https://calendar.fixture.invalid/event/{external_id}",
        "source_updated_at": "2026-09-09T09:00:00+02:00",
        "metadata": {"fixture": True},
    }


def external_events(start: str, end: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"start": start, "end": end})
    _, rows = json_request("GET", f"/v1/calendar/external-events?{query}")
    return rows


def main() -> None:
    wait_ready()

    first = event(
        "fixture-event-1",
        "External source title v1",
        "2026-09-10T09:30:00+02:00",
        "2026-09-10T10:30:00+02:00",
    )
    second = event(
        "fixture-event-2",
        "External all-day marker",
        "2026-09-11T00:00:00+02:00",
        "2026-09-12T00:00:00+02:00",
        all_day=True,
    )

    _, ingested = json_request(
        "POST",
        "/internal/v1/calendar/snapshot",
        payload=snapshot([first, second]),
        headers=INTERNAL,
    )
    assert ingested["received_events"] == 2, ingested
    assert ingested["removed_events"] == 0, ingested
    source_id = ingested["source"]["id"]
    assert ingested["source"]["provider"] == "google", ingested

    _, sources = json_request("GET", "/v1/calendar/sources")
    source = next(item for item in sources if item["id"] == source_id)
    assert source["key"] == "fixture.google-calendar", source
    assert source["external_account_ref"] == "fixture-account", source
    assert source["last_sync_at"], source

    rows = external_events("2026-09-09T00:00:00+02:00", "2026-09-13T00:00:00+02:00")
    assert len([row for row in rows if row["source_id"] == source_id]) == 2, rows
    first_row = next(row for row in rows if row["external_id"] == "fixture-event-1")
    original_event_id = first_row["id"]
    assert first_row["source_key"] == "fixture.google-calendar", first_row
    assert first_row["source_provider"] == "google", first_row
    assert first_row["source_display_name"] == "Google Calendar Fixture", first_row
    assert first_row["title"] == "External source title v1", first_row

    # Replaying the same external identity updates the snapshot in place rather than duplicating it.
    updated_first = {**first, "title": "External source title v2"}
    _, replay = json_request(
        "POST",
        "/internal/v1/calendar/snapshot",
        payload=snapshot([updated_first, second]),
        headers=INTERNAL,
    )
    assert replay["received_events"] == 2, replay
    rows = external_events("2026-09-09T00:00:00+02:00", "2026-09-13T00:00:00+02:00")
    replayed = next(row for row in rows if row["external_id"] == "fixture-event-1")
    assert replayed["id"] == original_event_id, replayed
    assert replayed["title"] == "External source title v2", replayed

    # A full snapshot can remove an externally deleted item without mutating KAIRO Tasks.
    _, replaced = json_request(
        "POST",
        "/internal/v1/calendar/snapshot",
        payload=snapshot([updated_first]),
        headers=INTERNAL,
    )
    assert replaced["removed_events"] == 1, replaced
    rows = external_events("2026-09-09T00:00:00+02:00", "2026-09-13T00:00:00+02:00")
    fixture_rows = [row for row in rows if row["source_id"] == source_id]
    assert [row["external_id"] for row in fixture_rows] == ["fixture-event-1"], fixture_rows

    # A source key is permanently bound to its external account identity.
    json_request(
        "POST",
        "/internal/v1/calendar/snapshot",
        expected=409,
        payload=snapshot([updated_first], account_ref="different-account"),
        headers=INTERNAL,
    )

    # Connector snapshots must provide timezone-aware instants.
    naive = event(
        "fixture-naive",
        "Naive timestamp",
        "2026-09-10T09:30:00",
        "2026-09-10T10:30:00",
    )
    json_request(
        "POST",
        "/internal/v1/calendar/snapshot",
        expected=422,
        payload=snapshot([naive]),
        headers=INTERNAL,
    )

    # Public reads are interval-bounded: events outside the requested range stay absent.
    assert external_events("2026-09-20T00:00:00+02:00", "2026-09-21T00:00:00+02:00") == []

    print("KAIRO external calendar provenance snapshot proof passed")


if __name__ == "__main__":
    main()
