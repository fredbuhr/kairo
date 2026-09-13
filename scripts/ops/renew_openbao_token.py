#!/usr/bin/env python3
"""Renew the production OpenBao workload token without printing secret material."""

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
from pathlib import Path


EXPECTED_POLICY = ["nevolium-core"]
EXPECTED_PERIOD_SECONDS = 604800
TOKEN = re.compile(r"s\.[A-Za-z0-9]{24,}")


def private_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError(f"fichier prive absent ou invalide : {path.name}")
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError(f"{path.name} doit appartenir a root en mode 0600")


def env_token(text: str) -> str:
    matches = [
        line.split("=", 1)[1]
        for line in text.splitlines()
        if line.startswith("OPENBAO_TOKEN=")
    ]
    if len(matches) != 1 or not TOKEN.fullmatch(matches[0]):
        raise RuntimeError("OPENBAO_TOKEN absent, duplique ou inattendu")
    return matches[0]


def workload_metadata(text: str) -> dict:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("metadonnees workload OpenBao inattendues")
    if (not isinstance(value.get("accessor"), str) or not value["accessor"]
            or value.get("display_name") != "nevolium-core"
            or value.get("period_seconds") != EXPECTED_PERIOD_SECONDS):
        raise RuntimeError("metadonnees workload OpenBao inattendues")
    return value


def validate_lookup(text: str, metadata: dict, minimum_ttl: int) -> int:
    value = json.loads(text)
    data = value.get("data") if isinstance(value, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("reponse lookup-self OpenBao inattendue")
    try:
        period = int(data.get("period") or 0)
        ttl = int(data.get("ttl") or 0)
    except (TypeError, ValueError):
        raise RuntimeError("durees du jeton OpenBao inattendues") from None
    if (data.get("accessor") != metadata["accessor"]
            or data.get("policies") != EXPECTED_POLICY
            or period != EXPECTED_PERIOD_SECONDS
            or data.get("renewable") is not True
            or data.get("orphan") is not True
            or ttl < minimum_ttl
            or ttl > EXPECTED_PERIOD_SECONDS):
        raise RuntimeError("identite, droits ou duree du jeton OpenBao inattendus")
    return ttl


def compose(base: list[str], args: list[str], *, stdin=None, allowed=(0,)):
    result = subprocess.run(
        [*base, *args], input=stdin, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode not in allowed:
        raise RuntimeError(f"commande OpenBao refusee (code {result.returncode})")
    return result


def bao_as(base: list[str], args: list[str], *, allowed=(0,)):
    shell = 'export BAO_TOKEN="$(cat "$1")"; shift; exec bao "$@"'
    return compose(
        base,
        ["exec", "-T", "openbao", "sh", "-ec", shell,
         "sh", "/tmp/nevolium-renew-token", *args],
        allowed=allowed,
    )


def exclusive_lock(path: Path):
    flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    metadata = os.fstat(descriptor)
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        os.close(descriptor)
        raise RuntimeError("verrou de renouvellement non prive")
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        raise RuntimeError("un renouvellement OpenBao est deja actif") from None
    return descriptor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path,
                        default=Path("/opt/nevolium/source"))
    parser.add_argument("--env-file", type=Path,
                        default=Path("/etc/nevolium/production.env"))
    parser.add_argument("--workload-meta", type=Path,
                        default=Path("/etc/nevolium/openbao-workload.json"))
    parser.add_argument("--minimum-ttl-seconds", type=int, default=518400)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("ARRET : cette procedure doit etre executee avec sudo.")
    if not 1 <= args.minimum_ttl_seconds <= EXPECTED_PERIOD_SECONDS:
        raise SystemExit("ARRET : seuil TTL invalide.")

    lock_descriptor = None
    try:
        project_root = args.project_root.resolve()
        env_file = args.env_file.absolute()
        workload_meta = args.workload_meta.absolute()
        for name in ("compose.yaml", "compose.production.yaml"):
            if not (project_root / name).is_file():
                raise RuntimeError(f"{name} absent du projet")
        base = [
            "docker", "compose", "--project-directory", str(project_root),
            "--env-file", str(env_file),
            "-f", str(project_root / "compose.yaml"),
            "-f", str(project_root / "compose.production.yaml"),
        ]
        private_file(env_file)
        private_file(workload_meta)
        token = env_token(env_file.read_text())
        metadata = workload_metadata(workload_meta.read_text())
        lock_descriptor = exclusive_lock(
            Path("/run/lock/nevolium-openbao-renew.lock")
        )

        status = json.loads(compose(
            base,
            ["exec", "-T", "openbao", "bao", "status", "-format=json"],
            allowed=(0, 2),
        ).stdout)
        if status.get("sealed") or not status.get("initialized"):
            raise RuntimeError("OpenBao n'est pas initialise et descelle")

        try:
            compose(
                base,
                ["exec", "-T", "openbao", "sh", "-ec",
                 "umask 077; cat > /tmp/nevolium-renew-token"],
                stdin=token + "\n",
            )
            token = None
            validate_lookup(
                bao_as(base, ["token", "lookup", "-format=json"]).stdout,
                metadata,
                1,
            )
            renewed = json.loads(bao_as(
                base, ["token", "renew", "-format=json"]
            ).stdout)
            if renewed.get("auth", {}).get("renewable") is not True:
                raise RuntimeError("le jeton renouvele n'est pas renouvelable")
            ttl = validate_lookup(
                bao_as(base, ["token", "lookup", "-format=json"]).stdout,
                metadata,
                args.minimum_ttl_seconds,
            )
        finally:
            compose(
                base,
                ["exec", "-T", "openbao", "sh", "-ec",
                 "rm -f /tmp/nevolium-renew-token"],
                allowed=(0, 1),
            )
    except (json.JSONDecodeError, OSError, RuntimeError) as exc:
        raise SystemExit(f"ARRET : {exc}") from None
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)

    print(
        "Jeton workload OpenBao renouvele et verifie : "
        f"periode {EXPECTED_PERIOD_SECONDS}s, TTL {ttl}s."
    )


if __name__ == "__main__":
    main()
