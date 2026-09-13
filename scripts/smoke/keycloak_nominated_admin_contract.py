"""Contract tests for nominated Keycloak realm-administrator provisioning."""

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "scripts" / "ops"

FIRST_SPEC = importlib.util.spec_from_file_location(
    "keycloak_first_user", OPS / "keycloak_first_user.py"
)
FIRST_MODULE = importlib.util.module_from_spec(FIRST_SPEC)
assert FIRST_SPEC.loader is not None
sys.modules["keycloak_first_user"] = FIRST_MODULE
FIRST_SPEC.loader.exec_module(FIRST_MODULE)

SPEC = importlib.util.spec_from_file_location(
    "keycloak_nominated_admin", OPS / "keycloak_nominated_admin.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


PROFILE = {
    "username": "pilot.admin",
    "email": "pilot.admin@example.com",
    "firstName": "Pilot",
    "lastName": "Admin",
}


class FakeAdmin:
    def __init__(self):
        self.count = 1
        self.users = {
            "standard-id": {
                "id": "standard-id",
                "username": "pilot.user",
                "email": "pilot@example.com",
                "enabled": True,
                "totp": True,
                "requiredActions": [],
            }
        }
        self.realm_mappings = {}
        self.client_mappings = {}
        self.deleted = []
        self.fail_client_role = False

    def user_count(self):
        return self.count

    def exact_users(self, username):
        return [user for user in self.users.values() if user["username"] == username]

    def exact_email_users(self, email):
        return [user for user in self.users.values() if user.get("email") == email]

    def realm_role(self, name):
        return {"id": f"realm-{name}", "name": name}

    def exact_clients(self, client_id):
        return [{"id": "realm-management-id", "clientId": client_id}]

    def client_role(self, client_uuid, name):
        return {"id": f"client-{name}", "name": name}

    def create_user(self, profile):
        self.users["admin-id"] = {"id": "admin-id", "totp": False, **profile}
        self.count += 1
        return "admin-id"

    def reset_password(self, user_id, password):
        if not password:
            raise RuntimeError("missing password")

    def assign_realm_role(self, user_id, role):
        self.realm_mappings[user_id] = [role]

    def assign_client_role(self, user_id, client_uuid, role):
        if self.fail_client_role:
            raise RuntimeError("synthetic client-role failure")
        self.client_mappings[(user_id, client_uuid)] = [role]

    def update_user(self, user_id, profile):
        self.users[user_id].update(profile)

    def user(self, user_id):
        return self.users[user_id]

    def realm_roles(self, user_id):
        return self.realm_mappings.get(user_id, [])

    def client_roles(self, user_id, client_uuid):
        return self.client_mappings.get((user_id, client_uuid), [])

    def delete_user(self, user_id):
        self.deleted.append(user_id)
        self.users.pop(user_id, None)
        self.count -= 1


class NominatedAdminContract(unittest.TestCase):
    def test_admin_is_disabled_until_both_roles_and_actions_are_set(self):
        api = FakeAdmin()
        MODULE.provision_administrator(api, PROFILE, "temporary-password")
        admin = api.users["admin-id"]
        self.assertTrue(admin["enabled"])
        self.assertFalse(admin["totp"])
        self.assertEqual(set(admin["requiredActions"]), MODULE.REQUIRED_ACTIONS)
        self.assertIn(
            MODULE.APPLICATION_ADMIN_ROLE,
            {role["name"] for role in api.realm_mappings["admin-id"]},
        )
        self.assertIn(
            MODULE.REALM_ADMIN_ROLE,
            {
                role["name"]
                for role in api.client_mappings[
                    ("admin-id", "realm-management-id")
                ]
            },
        )

    def test_partial_admin_is_removed_when_client_role_assignment_fails(self):
        api = FakeAdmin()
        api.fail_client_role = True
        with self.assertRaisesRegex(RuntimeError, "new identity was removed"):
            MODULE.provision_administrator(api, PROFILE, "temporary-password")
        self.assertEqual(api.deleted, ["admin-id"])
        self.assertNotIn("admin-id", api.users)

    def test_creation_requires_exactly_the_existing_standard_user(self):
        api = FakeAdmin()
        api.count = 2
        with self.assertRaisesRegex(RuntimeError, "exactly one existing"):
            MODULE.provision_administrator(api, PROFILE, "temporary-password")
        self.assertNotIn("admin-id", api.users)

    def test_duplicate_email_is_refused_before_creation(self):
        api = FakeAdmin()
        duplicate = {**PROFILE, "email": "pilot@example.com"}
        with self.assertRaisesRegex(RuntimeError, "email already exists"):
            MODULE.provision_administrator(api, duplicate, "temporary-password")
        self.assertNotIn("admin-id", api.users)

    def test_verification_requires_totp_actions_and_both_admin_roles(self):
        api = FakeAdmin()
        MODULE.provision_administrator(api, PROFILE, "temporary-password")
        with self.assertRaisesRegex(RuntimeError, "TOTP is not active"):
            MODULE.verify_administrator(api, PROFILE["username"])
        api.users["admin-id"].update(totp=True, requiredActions=[])
        MODULE.verify_administrator(api, PROFILE["username"])
        api.client_mappings[("admin-id", "realm-management-id")] = []
        with self.assertRaisesRegex(RuntimeError, "realm administration role is absent"):
            MODULE.verify_administrator(api, PROFILE["username"])


if __name__ == "__main__":
    unittest.main()
