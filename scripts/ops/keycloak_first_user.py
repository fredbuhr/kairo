#!/usr/bin/env python3
"""Create or verify the first production Nevolium user without exposing secrets."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener


LOCAL_KEYCLOAK = "http://127.0.0.1:8081"
ROLE = "nevolium-user"
REQUIRED_ACTIONS = frozenset({"UPDATE_PASSWORD", "CONFIGURE_TOTP"})
MAX_RESPONSE_BYTES = 1_048_576
USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError("invalid environment assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in values:
            raise RuntimeError("duplicate environment assignment")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def protected_env(path: Path) -> dict[str, str]:
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("environment file must be a regular file, not a symlink")
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError("environment file must be owned by root with mode 0600")
    values = parse_env(path.read_text(encoding="utf-8"))
    required = ("KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_PASSWORD", "KEYCLOAK_REALM")
    if any(not values.get(key) for key in required):
        raise RuntimeError("required Keycloak configuration is absent")
    if values["KEYCLOAK_REALM"] != "nevolium":
        raise RuntimeError("refusing to provision a different realm")
    if any("CHANGE_ME" in values[key] for key in required):
        raise RuntimeError("Keycloak bootstrap configuration is incomplete")
    return values


def clean_identity(value: str, label: str, maximum: int = 100) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(char) < 32 for char in cleaned):
        raise RuntimeError(f"invalid {label}")
    return cleaned


def validate_profile(profile: dict[str, str], bootstrap_username: str) -> None:
    if not USERNAME.fullmatch(profile["username"]):
        raise RuntimeError("username must use 3-64 lowercase letters, digits, dot, dash or underscore")
    if profile["username"] == bootstrap_username:
        raise RuntimeError("application and bootstrap usernames must be distinct")
    if len(profile["email"]) > 254 or not EMAIL.fullmatch(profile["email"]):
        raise RuntimeError("invalid email address")
    clean_identity(profile["firstName"], "first name")
    clean_identity(profile["lastName"], "last name")


class KeycloakAdmin:
    def __init__(self, origin: str, realm: str, username: str, password: str):
        if origin != LOCAL_KEYCLOAK:
            raise RuntimeError("Keycloak administration must use the local loopback endpoint")
        self.origin = origin
        self.realm = realm
        self.opener = build_opener(ProxyHandler({}))
        self.token = self._authenticate(username, password)

    def _read(self, response: Any) -> bytes:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Keycloak response exceeded the safety bound")
        return body

    def _send(
        self,
        method: str,
        url: str,
        *,
        payload: Any | None = None,
        form: dict[str, str] | None = None,
        token: bool = True,
    ) -> tuple[int, Any, bytes]:
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                return response.status, response.headers, self._read(response)
        except HTTPError as exc:
            exc.read(MAX_RESPONSE_BYTES)
            raise RuntimeError(f"Keycloak administration request failed with status {exc.code}") from None
        except (OSError, URLError) as exc:
            raise RuntimeError("Keycloak local administration endpoint is unavailable") from exc

    def _authenticate(self, username: str, password: str) -> str:
        status, _, body = self._send(
            "POST",
            f"{self.origin}/realms/master/protocol/openid-connect/token",
            form={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": username,
                "password": password,
            },
            token=False,
        )
        if status != 200:
            raise RuntimeError("Keycloak bootstrap authentication failed")
        token = json.loads(body).get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Keycloak bootstrap token is absent")
        return token

    def _admin(self, suffix: str) -> str:
        return f"{self.origin}/admin/realms/{quote(self.realm, safe='')}{suffix}"

    def _json(self, method: str, suffix: str, payload: Any | None = None) -> Any:
        status, _, body = self._send(method, self._admin(suffix), payload=payload)
        if status not in {200, 201, 204}:
            raise RuntimeError("unexpected Keycloak administration status")
        if not body:
            return None
        return json.loads(body)

    def user_count(self) -> int:
        value = self._json("GET", "/users/count")
        if not isinstance(value, int):
            raise RuntimeError("invalid Keycloak user count")
        return value

    def exact_users(self, username: str) -> list[dict[str, Any]]:
        query = urlencode({"username": username, "exact": "true", "max": "2"})
        users = self._json("GET", f"/users?{query}")
        if not isinstance(users, list):
            raise RuntimeError("invalid Keycloak user lookup")
        return users

    def realm_role(self, name: str) -> dict[str, Any]:
        role = self._json("GET", f"/roles/{quote(name, safe='')}")
        if not isinstance(role, dict) or role.get("name") != name or not role.get("id"):
            raise RuntimeError("required Nevolium role is absent")
        return role

    def create_user(self, profile: dict[str, Any]) -> str:
        status, headers, _ = self._send(
            "POST", self._admin("/users"), payload=profile
        )
        if status != 201:
            raise RuntimeError("Keycloak user creation failed")
        location = headers.get("Location", "").rstrip("/")
        user_id = location.rsplit("/", 1)[-1]
        if not user_id or user_id == "users" or "/" in user_id:
            raise RuntimeError("created Keycloak user identifier is absent")
        return user_id

    def reset_password(self, user_id: str, password: str) -> None:
        self._json(
            "PUT",
            f"/users/{quote(user_id, safe='')}/reset-password",
            {"type": "password", "value": password, "temporary": True},
        )

    def assign_realm_role(self, user_id: str, role: dict[str, Any]) -> None:
        self._json(
            "POST",
            f"/users/{quote(user_id, safe='')}/role-mappings/realm",
            [role],
        )

    def update_user(self, user_id: str, profile: dict[str, Any]) -> None:
        self._json("PUT", f"/users/{quote(user_id, safe='')}", profile)

    def user(self, user_id: str) -> dict[str, Any]:
        user = self._json("GET", f"/users/{quote(user_id, safe='')}")
        if not isinstance(user, dict):
            raise RuntimeError("invalid Keycloak user representation")
        return user

    def realm_roles(self, user_id: str) -> list[dict[str, Any]]:
        roles = self._json(
            "GET", f"/users/{quote(user_id, safe='')}/role-mappings/realm"
        )
        if not isinstance(roles, list):
            raise RuntimeError("invalid Keycloak role mapping")
        return roles

    def delete_user(self, user_id: str) -> None:
        self._json("DELETE", f"/users/{quote(user_id, safe='')}")


def provision_user(api: Any, profile: dict[str, str], password: str) -> None:
    if api.user_count() != 0:
        raise RuntimeError("the production realm is not empty; first-user provisioning refused")
    if api.exact_users(profile["username"]):
        raise RuntimeError("username already exists")
    role = api.realm_role(ROLE)
    disabled = {
        **profile,
        "enabled": False,
        "emailVerified": False,
        "requiredActions": sorted(REQUIRED_ACTIONS),
    }
    user_id = api.create_user(disabled)
    try:
        api.reset_password(user_id, password)
        api.assign_realm_role(user_id, role)
        api.update_user(user_id, {**disabled, "enabled": True})
        created = api.user(user_id)
        roles = {item.get("name") for item in api.realm_roles(user_id)}
        pending = set(created.get("requiredActions") or [])
        if (
            created.get("enabled") is not True
            or created.get("totp") is True
            or not REQUIRED_ACTIONS.issubset(pending)
            or ROLE not in roles
        ):
            raise RuntimeError("created user verification failed")
    except Exception as exc:
        try:
            api.delete_user(user_id)
        except Exception:
            raise RuntimeError(
                "provisioning failed and rollback could not be confirmed"
            ) from exc
        raise RuntimeError("provisioning failed; new identity was removed") from exc


def verify_user(api: Any, username: str) -> None:
    users = api.exact_users(username)
    if len(users) != 1:
        raise RuntimeError("expected exactly one matching Keycloak user")
    user = api.user(users[0]["id"])
    roles = {item.get("name") for item in api.realm_roles(user["id"])}
    pending = set(user.get("requiredActions") or [])
    if user.get("enabled") is not True or user.get("totp") is not True:
        raise RuntimeError("user or TOTP is not active")
    if pending:
        raise RuntimeError("an initial required action is still pending")
    if ROLE not in roles:
        raise RuntimeError("Nevolium user role is absent")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run this command as root")

    try:
        values = protected_env(Path(args.env_file))
        username = clean_identity(input("Nom d'utilisateur Nevolium : "), "username", 64)
        profile = None
        password = None
        if args.action == "create":
            profile = {
                "username": username,
                "email": clean_identity(input("Adresse email : "), "email", 254),
                "firstName": clean_identity(input("Prénom : "), "first name"),
                "lastName": clean_identity(input("Nom : "), "last name"),
            }
            validate_profile(profile, values["KEYCLOAK_ADMIN"])
            password = getpass.getpass("Mot de passe temporaire : ")
            confirmation = getpass.getpass("Confirmez le mot de passe temporaire : ")
            if password != confirmation:
                raise RuntimeError("password confirmation differs")
            if len(password) < 16 or len(password) > 1024:
                raise RuntimeError("temporary password must contain 16-1024 characters")

        api = KeycloakAdmin(
            LOCAL_KEYCLOAK,
            values["KEYCLOAK_REALM"],
            values["KEYCLOAK_ADMIN"],
            values["KEYCLOAK_ADMIN_PASSWORD"],
        )
        if args.action == "create":
            provision_user(api, profile, password)
            print("PREMIER_UTILISATEUR_KEYCLOAK_CREE")
            print("ROLE_NEVOLIUM_USER_ATTRIBUE")
            print("CHANGEMENT_MOT_DE_PASSE_ET_TOTP_REQUIS")
        else:
            validate_profile(
                {
                    "username": username,
                    "email": "placeholder@example.invalid",
                    "firstName": "placeholder",
                    "lastName": "placeholder",
                },
                values["KEYCLOAK_ADMIN"],
            )
            verify_user(api, username)
            print("UTILISATEUR_NEVOLIUM_ACTIF")
            print("TOTP_CONFIGURE")
            print("ACTIONS_INITIALES_TERMINEES")
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
        password = None


if __name__ == "__main__":
    main()
