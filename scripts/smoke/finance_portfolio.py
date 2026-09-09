#!/usr/bin/env python3
"""Proof for provenance-preserving Finance/Crypto snapshots and unsigned proposal isolation."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from decimal import Decimal
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
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    body = json.loads(raw) if raw else None
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


def decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def source(*, account_ref: str = "rotki-local-fixture", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "key": "fixture.rotki",
        "provider": "rotki",
        "source_type": "portfolio",
        "external_account_ref": account_ref,
        "display_name": "Rotki Fixture",
        "status": "connected",
        "metadata": metadata or {"fixture": True, "adapter": "normalized-snapshot"},
    }


def account(
    external_id: str,
    label: str,
    account_type: str,
    *,
    network: str | None = None,
    address: str | None = None,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "label": label,
        "account_type": account_type,
        "network": network,
        "public_address": address,
        "metadata": {"fixture": True},
    }


def position(
    account_external_id: str,
    asset_key: str,
    symbol: str,
    quantity: str,
    price: str,
    value: str,
    cost: str,
    pnl: str,
    *,
    name: str | None = None,
    asset_type: str = "crypto",
) -> dict[str, Any]:
    return {
        "account_external_id": account_external_id,
        "asset_key": asset_key,
        "symbol": symbol,
        "name": name,
        "asset_type": asset_type,
        "quantity": quantity,
        "unit_price_usd": price,
        "value_usd": value,
        "cost_basis_usd": cost,
        "unrealized_pnl_usd": pnl,
        "metadata": {"fixture": True},
    }


def snapshot(
    accounts: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    *,
    account_ref: str = "rotki-local-fixture",
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "owner_subject": OWNER,
        "source": source(account_ref=account_ref, metadata=source_metadata),
        "accounts": accounts,
        "positions": positions,
        "replace_missing": True,
    }


def portfolio() -> dict[str, Any]:
    _, body = json_request("GET", "/v1/finance/portfolio")
    return body


def main() -> None:
    wait_ready()

    wallet = account(
        "wallet-ethereum",
        "Cold Wallet (public observation)",
        "wallet",
        network="ethereum",
        address="0x1111111111111111111111111111111111111111",
    )
    exchange = account("exchange-main", "Exchange Fixture", "exchange")
    eth = position(
        "wallet-ethereum",
        "ethereum:eth",
        "ETH",
        "2.000000000000000000",
        "2500",
        "5000",
        "4000",
        "1000",
        name="Ethereum",
    )
    usdc = position(
        "wallet-ethereum",
        "ethereum:usdc",
        "USDC",
        "1000",
        "1",
        "1000",
        "1000",
        "0",
        name="USD Coin",
        asset_type="stablecoin",
    )
    btc = position(
        "exchange-main",
        "bitcoin:btc",
        "BTC",
        "0.1",
        "60000",
        "6000",
        "5000",
        "1000",
        name="Bitcoin",
    )

    _, ingested = json_request(
        "POST",
        "/internal/v1/finance/snapshot",
        payload=snapshot([wallet, exchange], [eth, usdc, btc]),
        headers=INTERNAL,
    )
    assert ingested["received_accounts"] == 2, ingested
    assert ingested["received_positions"] == 3, ingested
    assert ingested["removed_accounts"] == 0, ingested
    assert ingested["removed_positions"] == 0, ingested
    source_id = ingested["source"]["id"]
    assert ingested["source"]["provider"] == "rotki", ingested

    first = portfolio()
    assert decimal(first["total_value_usd"]) == Decimal("12000"), first
    assert decimal(first["total_cost_basis_usd"]) == Decimal("10000"), first
    assert decimal(first["total_unrealized_pnl_usd"]) == Decimal("2000"), first
    assert len(first["sources"]) == 1, first
    assert len(first["accounts"]) == 2, first
    assert len(first["positions"]) == 3, first
    wallet_read = next(item for item in first["accounts"] if item["external_id"] == "wallet-ethereum")
    wallet_id = wallet_read["id"]
    eth_read = next(item for item in first["positions"] if item["asset_key"] == "ethereum:eth")
    eth_id = eth_read["id"]
    assert eth_read["source_id"] == source_id, eth_read
    assert eth_read["source_key"] == "fixture.rotki", eth_read
    assert eth_read["source_provider"] == "rotki", eth_read
    assert eth_read["account_id"] == wallet_id, eth_read
    assert eth_read["public_address"] == wallet["public_address"], eth_read

    # Provider replay updates the same observed account/position identities rather than duplicating.
    updated_eth = {**eth, "unit_price_usd": "2600", "value_usd": "5200", "unrealized_pnl_usd": "1200"}
    json_request(
        "POST",
        "/internal/v1/finance/snapshot",
        payload=snapshot([wallet, exchange], [updated_eth, usdc, btc]),
        headers=INTERNAL,
    )
    replayed = portfolio()
    replay_wallet = next(item for item in replayed["accounts"] if item["external_id"] == "wallet-ethereum")
    replay_eth = next(item for item in replayed["positions"] if item["asset_key"] == "ethereum:eth")
    assert replay_wallet["id"] == wallet_id, replay_wallet
    assert replay_eth["id"] == eth_id, replay_eth
    assert decimal(replay_eth["value_usd"]) == Decimal("5200"), replay_eth

    # A complete sourced snapshot may remove missing observations. This only changes the finance
    # read model; it does not fabricate transactions or modify unrelated KAIRO Tasks.
    _, replaced = json_request(
        "POST",
        "/internal/v1/finance/snapshot",
        payload=snapshot([wallet], [updated_eth]),
        headers=INTERNAL,
    )
    assert replaced["removed_accounts"] == 1, replaced
    assert replaced["removed_positions"] == 2, replaced
    compact = portfolio()
    assert [item["external_id"] for item in compact["accounts"]] == ["wallet-ethereum"], compact
    assert [item["asset_key"] for item in compact["positions"]] == ["ethereum:eth"], compact
    assert decimal(compact["total_value_usd"]) == Decimal("5200"), compact

    # A source key cannot silently change provider account identity.
    json_request(
        "POST",
        "/internal/v1/finance/snapshot",
        expected=409,
        payload=snapshot([wallet], [updated_eth], account_ref="other-rotki-account"),
        headers=INTERNAL,
    )

    # Finance metadata is not a secret storage channel. Public addresses are allowed; private keys,
    # seeds and provider credentials are rejected before any row is written.
    json_request(
        "POST",
        "/internal/v1/finance/snapshot",
        expected=422,
        payload=snapshot(
            [wallet],
            [updated_eth],
            source_metadata={"fixture": True, "private_key": "must-never-enter-kairo"},
        ),
        headers=INTERNAL,
    )

    _, project = json_request(
        "POST",
        "/v1/projects",
        expected=201,
        payload={
            "name": "Finance Signing Isolation Fixture",
            "status": "active",
            "summary": "Unsigned finance proposal proof",
            "parent_id": None,
        },
    )

    # KAIRO may prepare an unsigned transfer draft only for an asset actually observed on the
    # selected account. The response must explicitly preserve the external signing boundary.
    _, proposal = json_request(
        "POST",
        "/v1/finance/transaction-proposals",
        expected=201,
        payload={
            "project_id": project["id"],
            "from_account_id": wallet_id,
            "kind": "crypto_transfer",
            "network": "ethereum",
            "asset_key": "ethereum:eth",
            "symbol": "ETH",
            "amount": "0.125000000000000001",
            "destination": "0x2222222222222222222222222222222222222222",
            "memo": "Unsigned smoke proposal",
            "simulation": {"fixture": True},
        },
    )
    assert proposal["status"] == "draft", proposal
    assert proposal["signing_required"] is True, proposal
    assert proposal["signing_boundary"] == "external_isolated_signer", proposal
    assert decimal(proposal["amount"]) == Decimal("0.125000000000000001"), proposal
    assert proposal["simulation_json"]["observed_position_id"] == eth_id, proposal
    assert proposal["simulation_json"]["observed_at"], proposal

    _, proposals = json_request("GET", "/v1/finance/transaction-proposals")
    listed = next(item for item in proposals if item["id"] == proposal["id"])
    assert listed["signing_required"] is True, listed
    assert listed["signing_boundary"] == "external_isolated_signer", listed

    # A request cannot invent an asset that is absent from the latest sourced observation.
    json_request(
        "POST",
        "/v1/finance/transaction-proposals",
        expected=409,
        payload={
            "from_account_id": wallet_id,
            "network": "ethereum",
            "asset_key": "ethereum:usdc",
            "symbol": "USDC",
            "amount": "1",
            "destination": "0x3333333333333333333333333333333333333333",
            "simulation": {},
        },
    )

    # The same observed asset cannot be relabeled while preparing a draft.
    json_request(
        "POST",
        "/v1/finance/transaction-proposals",
        expected=409,
        payload={
            "from_account_id": wallet_id,
            "network": "ethereum",
            "asset_key": "ethereum:eth",
            "symbol": "FAKEETH",
            "amount": "0.01",
            "destination": "0x4444444444444444444444444444444444444444",
            "simulation": {},
        },
    )

    print("KAIRO sourced Finance portfolio + unsigned signing-isolation proof passed")


if __name__ == "__main__":
    main()
