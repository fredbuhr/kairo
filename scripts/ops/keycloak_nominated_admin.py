#!/usr/bin/env python3
"""Create or verify the nominated administrator for the Nevolium realm."""

import argparse
import getpass
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from keycloak_first_user import (
    LOCAL_KEYCLOAK,
    REQUIRED_ACTIONS,
    KeycloakAdmin,
    clean_identity,
    protected_env,
    validate_email,
    validate_username,
)


APPLICATION_ADMIN_ROLE = "nevolium-admin"
REALM_MANAGEMENT_CLIENT = "realm-management"
REALM_ADMIN_ROLE = "realm-admin"


class NominatedAdminApi(KeycloakAdmin):
    def exact_clients(self, client_id: str) -> list[dict[str, Any]]:
        query = urlencode({"clientId": client_id, "max": "2"})
        clients = self._json("GET", f"/clients?{query}")
        if not isinstance(clients, list):
            raise RuntimeError("invalid Keycloak client lookup")
        return clients

    def client_role(self, client_uuid: str, name: str) -> dict[str, Any]:
        role = self._json(
            "GET",
            f"/clients/{quote(client_uuid, safe='')}/roles/{quote(name, safe='')}",
        )
        if not isinstance(role, dict) or role.get("name") != name or not role.get("id"):
            raise RuntimeError("required Keycloak client role is absent")
        return role

    def assign_client_role(
        self, user_id: str, client_uuid: str, role: dict[str, Any]
    ) -> None:
        self._json(
            "POST",
            (
                f"/users/{quote(user_id, safe='')}/role-mappings/clients/"
                f"{quote(client_uuid, safe='')}"
            ),
            [role],
        )

    def client_roles(self, user_id: str, client_uuid: str) -> list[dict[str, Any]]:
        roles = self._json(
            "GET",
            (
                f"/users/{quote(user_id, safe='')}/role-mappings/clients/"
                f"{quote(client_uuid, safe='')}"
            ),
        )
        if not isinstance(roles, list):
            raise RuntimeError("invalid Keycloak client role mapping")
        return roles


def realm_management(api: Any) -> tuple[str, dict[str, Any]]:
    clients = api.exact_clients(REALM_MANAGEMENT_CLIENT)
    if len(clients) != 1:
        raise RuntimeError("expected exactly one realm-management client")
    client_uuid = clients[0].get("id")
    if not isinstance(client_uuid, str) or not client_uuid:
        raise RuntimeError("realm-management client identifier is absent")
    return client_uuid, api.client_role(client_uuid, REALM_ADMIN_ROLE)


def provision_administrator(
    api: Any, profile: dict[str, str], password: str
) -> None:
    if api.user_count() != 1:
        raise RuntimeError("expected exactly one existing production user")
    if api.exact_users(profile["username"]):
        raise RuntimeError("administrator username already exists")
    if api.exact_email_users(profile["email"]):
        raise RuntimeError("administrator email already exists")

    application_role = api.realm_role(APPLICATION_ADMIN_ROLE)
    client_uuid, realm_admin_role = realm_management(api)
    disabled = {
        **profile,
        "enabled": False,
        "emailVerified": False,
        "requiredActions": sorted(REQUIRED_ACTIONS),
    }
    user_id = api.create_user(disabled)
    try:
        api.reset_password(user_id, password)
        api.assign_realm_role(user_id, application_role)
        api.assign_client_role(user_id, client_uuid, realm_admin_role)
        api.update_user(user_id, {**disabled, "enabled": True})

        created = api.user(user_id)
        realm_roles = {item.get("name") for item in api.realm_roles(user_id)}
        client_roles = {
            item.get("name") for item in api.client_roles(user_id, client_uuid)
        }
        pending = set(created.get("requiredActions") or [])
        if (
            created.get("enabled") is not True
            or created.get("totp") is True
            or pending != REQUIRED_ACTIONS
            or APPLICATION_ADMIN_ROLE not in realm_roles
            or REALM_ADMIN_ROLE not in client_roles
        ):
            raise RuntimeError("created administrator verification failed")
    except Exception as exc:
        try:
            api.delete_user(user_id)
        except Exception:
            raise RuntimeError(
                "administrator provisioning failed and rollback could not be confirmed"
            ) from exc
        raise RuntimeError(
            "administrator provisioning failed; new identity was removed"
        ) from exc


def verify_administrator(api: Any, username: str) -> None:
    if api.user_count() != 2:
        raise RuntimeError("expected exactly two production realm users")
    users = api.exact_users(username)
    if len(users) != 1:
        raise RuntimeError("expected exactly one matching administrator")
    user = api.user(users[0]["id"])
    client_uuid, _ = realm_management(api)
    realm_roles = {item.get("name") for item in api.realm_roles(user["id"])}
    client_roles = {
        item.get("name") for item in api.client_roles(user["id"], client_uuid)
    }
    pending = set(user.get("requiredActions") or [])
    if user.get("enabled") is not True or user.get("totp") is not True:
        raise RuntimeError("administrator or TOTP is not active")
    if pending:
        raise RuntimeError("an administrator initial action is still pending")
    if APPLICATION_ADMIN_ROLE not in realm_roles:
        raise RuntimeError("Nevolium administrator role is absent")
    if REALM_ADMIN_ROLE not in client_roles:
        raise RuntimeError("realm administration role is absent")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run this command as root")

    try:
        values = protected_env(Path(args.env_file))
        username = clean_identity(
            input("Nom d'utilisateur administrateur Nevolium : "), "username", 64
        )
        validate_username(username, values["KEYCLOAK_ADMIN"])
        profile = None
        password = None
        if args.action == "create":
            profile = {
                "username": username,
                "email": clean_identity(
                    input("Adresse email administrateur : "), "email", 254
                ),
                "firstName": clean_identity(input("Prénom : "), "first name"),
                "lastName": clean_identity(input("Nom : "), "last name"),
            }
            validate_email(profile["email"])
            password = getpass.getpass("Mot de passe temporaire administrateur : ")
            confirmation = getpass.getpass(
                "Confirmez le mot de passe temporaire administrateur : "
            )
            if password != confirmation:
                raise RuntimeError("password confirmation differs")
            if len(password) < 16 or len(password) > 1024:
                raise RuntimeError("temporary password must contain 16-1024 characters")

        api = NominatedAdminApi(
            LOCAL_KEYCLOAK,
            values["KEYCLOAK_REALM"],
            values["KEYCLOAK_ADMIN"],
            values["KEYCLOAK_ADMIN_PASSWORD"],
        )
        if args.action == "create":
            provision_administrator(api, profile, password)
            print("ADMINISTRATEUR_NOMINATIF_KEYCLOAK_CREE")
            print("ROLE_NEVOLIUM_ADMIN_ATTRIBUE")
            print("ROLE_REALM_ADMIN_ATTRIBUE")
            print("CHANGEMENT_MOT_DE_PASSE_ET_TOTP_ADMIN_REQUIS")
        else:
            verify_administrator(api, username)
            print("ADMINISTRATEUR_NOMINATIF_ACTIF")
            print("TOTP_ADMINISTRATEUR_CONFIGURE")
            print("DROITS_REALM_ADMIN_CONFIRMES")
            print("ACTIONS_INITIALES_ADMIN_TERMINEES")
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
