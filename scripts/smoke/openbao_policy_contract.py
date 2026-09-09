#!/usr/bin/env python3
"""Fail-fast contract proof for the production KAIRO Core OpenBao user-secret policy."""

from pathlib import Path
import re

POLICY = Path("infrastructure/openbao/policies/kairo-core-user-secrets.hcl")


def block(text: str, path: str) -> str:
    pattern = re.compile(
        rf'path\s+"{re.escape(path)}"\s*\{{(?P<body>.*?)\}}',
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise AssertionError(f"Missing OpenBao policy block: {path}")
    return match.group("body")


def capabilities(body: str) -> set[str]:
    match = re.search(r"capabilities\s*=\s*\[(?P<items>.*?)\]", body, re.DOTALL)
    if not match:
        raise AssertionError("Policy block has no capabilities list")
    return set(re.findall(r'"([a-z_]+)"', match.group("items")))


def main() -> None:
    text = POLICY.read_text(encoding="utf-8")

    data_caps = capabilities(block(text, "secret/data/kairo/users/*"))
    metadata_caps = capabilities(block(text, "secret/metadata/kairo/users/*"))

    assert data_caps == {"create", "update", "read"}, data_caps
    assert metadata_caps == {"read", "delete"}, metadata_caps

    # These capabilities are deliberately absent from the KAIRO Core workload token. In particular,
    # `list` would make the user-secret namespace enumerable and `sudo` would collapse the boundary.
    forbidden_caps = {"sudo", "list", "patch"}
    assert not (data_caps & forbidden_caps), data_caps
    assert not (metadata_caps & forbidden_caps), metadata_caps

    declared_paths = re.findall(r'^\s*path\s+"([^"]+)"', text, re.MULTILINE)
    assert declared_paths == [
        "secret/data/kairo/users/*",
        "secret/metadata/kairo/users/*",
    ], declared_paths
    assert all(not path.startswith(("sys/", "auth/")) for path in declared_paths)
    assert all(path != "secret/*" for path in declared_paths)

    print("KAIRO OpenBao least-privilege user-secret policy contract passed")


if __name__ == "__main__":
    main()
