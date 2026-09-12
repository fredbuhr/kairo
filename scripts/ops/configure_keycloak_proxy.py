#!/usr/bin/env python3
"""Bind Keycloak's trusted proxy to the exact private Docker ingress gateway."""

import argparse
import ipaddress
import os
from pathlib import Path
import stat
import subprocess
import tempfile


KEY = "KEYCLOAK_PROXY_TRUSTED_ADDRESSES"
PLACEHOLDER = "CHANGE_ME_PROXY_ADDRESS"


def exact_private_ipv4(value: str) -> str:
    address = ipaddress.ip_address(value.strip())
    if (
        address.version != 4
        or not address.is_private
        or address.is_unspecified
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    ):
        raise RuntimeError("ingress gateway is not a private IPv4 address")
    return f"{address}/32"


def render_env(text: str, trusted_proxy: str) -> tuple[str, bool]:
    trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith(f"{KEY}=")]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {KEY} assignment")
    index = matches[0]
    current = lines[index].split("=", 1)[1]
    if current == trusted_proxy:
        return text, False
    if current != PLACEHOLDER:
        raise RuntimeError(f"refusing to replace an existing {KEY} value")
    lines[index] = f"{KEY}={trusted_proxy}"
    rendered = "\n".join(lines) + ("\n" if trailing_newline else "")
    return rendered, True


def command_output(arguments: list[str]) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("required Docker state could not be inspected")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--network", default="nevolium_ingress")
    parser.add_argument("--container", default="nevolium-keycloak-1")
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run this command as root")

    env_path = Path(args.env_file)
    metadata = env_path.lstat()
    if env_path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise SystemExit("Environment file must be a regular file, not a symlink")
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise SystemExit("Environment file must be owned by root with mode 0600")

    container = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", args.container],
        capture_output=True,
        text=True,
    )
    if container.returncode == 0 and container.stdout.strip() == "true":
        raise SystemExit("Stop Keycloak before changing its trusted proxy")

    gateway = command_output(
        [
            "docker",
            "network",
            "inspect",
            args.network,
            "--format",
            "{{(index .IPAM.Config 0).Gateway}}",
        ]
    )
    trusted_proxy = exact_private_ipv4(gateway)
    rendered, changed = render_env(env_path.read_text(encoding="utf-8"), trusted_proxy)
    if not changed:
        print("Keycloak trusted proxy already matches the private ingress gateway")
        return

    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=env_path.parent,
            prefix=f".{env_path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.fchmod(temporary.fileno(), 0o600)
            os.fchown(temporary.fileno(), metadata.st_uid, metadata.st_gid)
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, env_path)
        directory_fd = os.open(env_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)

    print("Keycloak trusted proxy bound to the private ingress gateway")


if __name__ == "__main__":
    main()
