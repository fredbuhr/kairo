"""Contract tests for irreversible Keycloak master-bootstrap retirement."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "scripts" / "ops"

for module_name in ("keycloak_first_user", "keycloak_nominated_admin"):
    spec = importlib.util.spec_from_file_location(module_name, OPS / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

SPEC = importlib.util.spec_from_file_location(
    "retire_keycloak_bootstrap", OPS / "retire_keycloak_bootstrap.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TargetApi:
    def __init__(self):
        self.users = {
            "user-id": {
                "id": "user-id", "username": "pilot.user", "enabled": True,
                "totp": True, "requiredActions": [],
            },
            "admin-id": {
                "id": "admin-id", "username": "pilot.admin", "enabled": True,
                "totp": True, "requiredActions": [],
            },
        }
        self.realm_mappings = {
            "user-id": [{"name": "nevolium-user"}],
            "admin-id": [{"name": "nevolium-admin"}],
        }
        self.client_mappings = {
            ("admin-id", "realm-management-id"): [{"name": "realm-admin"}]
        }

    def user_count(self):
        return len(self.users)

    def exact_users(self, username):
        return [user for user in self.users.values() if user["username"] == username]

    def user(self, user_id):
        return self.users[user_id]

    def realm_roles(self, user_id):
        return self.realm_mappings.get(user_id, [])

    def exact_clients(self, client_id):
        return [{"id": "realm-management-id", "clientId": client_id}]

    def client_role(self, client_uuid, name):
        return {"id": "realm-admin-id", "name": name}

    def client_roles(self, user_id, client_uuid):
        return self.client_mappings.get((user_id, client_uuid), [])


class MasterApi:
    def __init__(self):
        self.users = {
            "bootstrap-id": {
                "id": "bootstrap-id", "username": "bootstrap", "enabled": True,
            }
        }
        self.deleted = []

    def exact_users(self, username):
        return [user for user in self.users.values() if user["username"] == username]

    def user(self, user_id):
        return self.users[user_id]

    def delete_user(self, user_id):
        self.deleted.append(user_id)
        self.users.pop(user_id)


class BootstrapRetirementContract(unittest.TestCase):
    def test_retirement_requires_both_mfa_identities_then_rejection_and_scrub(self):
        target = TargetApi()
        master = MasterApi()
        committed = []
        MODULE.retire_bootstrap(
            target, master, "pilot.user", "pilot.admin", "bootstrap",
            MODULE.CONFIRMATION, lambda: True, lambda: committed.append(True),
        )
        self.assertEqual(master.deleted, ["bootstrap-id"])
        self.assertEqual(committed, [True])

    def test_wrong_confirmation_preserves_bootstrap_and_environment(self):
        target = TargetApi()
        master = MasterApi()
        committed = []
        with self.assertRaisesRegex(RuntimeError, "confirmation differs"):
            MODULE.retire_bootstrap(
                target, master, "pilot.user", "pilot.admin", "bootstrap",
                "NO", lambda: True, lambda: committed.append(True),
            )
        self.assertEqual(master.deleted, [])
        self.assertEqual(committed, [])

    def test_incomplete_admin_preserves_bootstrap(self):
        target = TargetApi()
        target.client_mappings.clear()
        master = MasterApi()
        with self.assertRaisesRegex(RuntimeError, "realm administration role is absent"):
            MODULE.retire_bootstrap(
                target, master, "pilot.user", "pilot.admin", "bootstrap",
                MODULE.CONFIRMATION, lambda: True, lambda: None,
            )
        self.assertEqual(master.deleted, [])

    def test_environment_is_not_committed_unless_old_login_is_rejected(self):
        target = TargetApi()
        master = MasterApi()
        committed = []
        with self.assertRaisesRegex(RuntimeError, "credentials were not rejected"):
            MODULE.retire_bootstrap(
                target, master, "pilot.user", "pilot.admin", "bootstrap",
                MODULE.CONFIRMATION, lambda: False, lambda: committed.append(True),
            )
        self.assertEqual(master.deleted, ["bootstrap-id"])
        self.assertEqual(committed, [])

    def test_environment_scrub_is_prepared_root_only_and_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "production.env"
            path.write_text(
                "KEYCLOAK_ADMIN=bootstrap\n"
                "KEYCLOAK_ADMIN_PASSWORD=abcdefghijklmnopqrstuvwxyz123456\n"
                "KEYCLOAK_REALM=nevolium\n"
                "KEEP=value\n",
                encoding="utf-8",
            )
            path.chmod(0o600)
            values, prepared = MODULE.prepare_scrubbed_environment(path)
            self.assertEqual(values["KEYCLOAK_ADMIN"], "bootstrap")
            self.assertEqual(
                prepared.read_text(encoding="utf-8"),
                "KEYCLOAK_REALM=nevolium\nKEEP=value\n",
            )
            self.assertEqual(prepared.stat().st_mode & 0o777, 0o600)
            MODULE.commit_scrubbed_environment(prepared, path)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "KEYCLOAK_REALM=nevolium\nKEEP=value\n",
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
