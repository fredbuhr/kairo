#!/usr/bin/env python3
"""Retire the master bootstrap after proving nominated Nevolium administration."""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from keycloak_first_user import (
    LOCAL_KEYCLOAK,
    KeycloakAdmin,
    clean_identity,
    protected_env,
    validate_username,
    verify_user,
)
from keycloak_nominated_admin import NominatedAdminApi, verify_administrator


CONFIRMATION = "RETIRER LE BOOTSTRAP"
BOOTSTRAP_KEYS = frozenset({"KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_PASSWORD"})
ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
MAX_RESPONSE_BYTES = 1_048_576


def prepare_scrubbed_environment(path: Path) -> tuple[dict[str, str], Path]:
    values = protected_env(path)
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("environment file must be a regular file, not a symlink")

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    found: dict[str, int] = {key: 0 for key in BOOTSTRAP_KEYS}
    retained: list[str] = []
    for line in lines:
        match = ASSIGNMENT.match(line)
        key = match.group(1) if match else None
        if key in BOOTSTRAP_KEYS:
            found[key] += 1
        else:
            retained.append(line)
    if found != {key: 1 for key in BOOTSTRAP_KEYS}:
        raise RuntimeError("expected exactly one assignment for each bootstrap credential")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".nevolium-bootstrap-retirement-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.writelines(retained)
            stream.flush()
            os.fsync(stream.fileno())
        scrubbed = temporary.read_text(encoding="utf-8")
        if any(ASSIGNMENT.match(line) and ASSIGNMENT.match(line).group(1) in BOOTSTRAP_KEYS
               for line in scrubbed.splitlines()):
            raise RuntimeError("prepared environment still contains bootstrap credentials")
        return values, temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def commit_scrubbed_environment(temporary: Path, destination: Path) -> None:
    metadata = temporary.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError("prepared environment permissions changed")
    os.replace(temporary, destination)
    directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def bootstrap_login_rejected(username: str, password: str) -> bool:
    opener = build_opener(ProxyHandler({}))
    request = Request(
        f"{LOCAL_KEYCLOAK}/realms/master/protocol/openid-connect/token",
        data=urlencode(
            {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": username,
                "password": password,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=10) as response:
            response.read(MAX_RESPONSE_BYTES + 1)
            return False
    except HTTPError as exc:
        body = exc.read(MAX_RESPONSE_BYTES)
        try:
            error = json.loads(body).get("error")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return exc.code in {400, 401} and error == "invalid_grant"
    except (OSError, URLError) as exc:
        raise RuntimeError("Keycloak local authentication endpoint is unavailable") from exc


def retire_bootstrap(
    target_api: Any,
    master_api: Any,
    standard_username: str,
    administrator_username: str,
    bootstrap_username: str,
    confirmation: str,
    login_rejected: Callable[[], bool],
    commit_environment: Callable[[], None],
) -> None:
    if standard_username == administrator_username:
        raise RuntimeError("standard and administrator usernames must be distinct")
    verify_user(target_api, standard_username)
    verify_administrator(target_api, administrator_username)

    bootstrap_users = master_api.exact_users(bootstrap_username)
    if len(bootstrap_users) != 1:
        raise RuntimeError("expected exactly one matching master bootstrap administrator")
    bootstrap = master_api.user(bootstrap_users[0]["id"])
    if bootstrap.get("enabled") is not True or bootstrap.get("username") != bootstrap_username:
        raise RuntimeError("master bootstrap administrator is not active or exact")
    if confirmation != CONFIRMATION:
        raise RuntimeError("bootstrap retirement confirmation differs")

    master_api.delete_user(bootstrap["id"])
    if not login_rejected():
        raise RuntimeError("deleted bootstrap credentials were not rejected")
    commit_environment()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run this command as root")

    environment = Path(args.env_file)
    temporary: Path | None = None
    values: dict[str, str] = {}
    target_api: NominatedAdminApi | None = None
    master_api: KeycloakAdmin | None = None
    try:
        values, temporary = prepare_scrubbed_environment(environment)
        standard_username = clean_identity(
            input("Nom d'utilisateur Nevolium standard : "), "username", 64
        )
        administrator_username = clean_identity(
            input("Nom d'utilisateur administrateur Nevolium : "), "username", 64
        )
        validate_username(standard_username, values["KEYCLOAK_ADMIN"])
        validate_username(administrator_username, values["KEYCLOAK_ADMIN"])

        target_api = NominatedAdminApi(
            LOCAL_KEYCLOAK,
            values["KEYCLOAK_REALM"],
            values["KEYCLOAK_ADMIN"],
            values["KEYCLOAK_ADMIN_PASSWORD"],
        )
        master_api = KeycloakAdmin(
            LOCAL_KEYCLOAK,
            "master",
            values["KEYCLOAK_ADMIN"],
            values["KEYCLOAK_ADMIN_PASSWORD"],
        )
        verify_user(target_api, standard_username)
        verify_administrator(target_api, administrator_username)
        bootstrap_users = master_api.exact_users(values["KEYCLOAK_ADMIN"])
        if len(bootstrap_users) != 1:
            raise RuntimeError("expected exactly one matching master bootstrap administrator")
        print("COMPTES_NOMINATIFS_ET_MFA_VALIDES")
        print("BOOTSTRAP_MASTER_IDENTIFIE_UNIQUEMENT")
        confirmation = input(f"Tapez exactement {CONFIRMATION} : ")

        retire_bootstrap(
            target_api,
            master_api,
            standard_username,
            administrator_username,
            values["KEYCLOAK_ADMIN"],
            confirmation,
            lambda: bootstrap_login_rejected(
                values["KEYCLOAK_ADMIN"], values["KEYCLOAK_ADMIN_PASSWORD"]
            ),
            lambda: commit_scrubbed_environment(temporary, environment),
        )
        temporary = None
        print("ADMINISTRATEUR_BOOTSTRAP_SUPPRIME")
        print("AUTHENTIFICATION_BOOTSTRAP_REFUSEE")
        print("IDENTIFIANTS_BOOTSTRAP_RETIRES_DE_ENV")
    except (
        EOFError,
        KeyboardInterrupt,
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise SystemExit(f"ARRET : {exc}") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if target_api is not None:
            target_api.token = ""
        if master_api is not None:
            master_api.token = ""
        values = {}


if __name__ == "__main__":
    main()
