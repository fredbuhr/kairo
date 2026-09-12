"""Contract tests for safe first-user Keycloak provisioning."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ops" / "keycloak_first_user.py"
SPEC = importlib.util.spec_from_file_location("keycloak_first_user", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


PROFILE = {
    "username": "pilot.user",
    "email": "pilot@example.com",
    "firstName": "Pilot",
    "lastName": "User",
}


class FakeAdmin:
    def __init__(self):
        self.count = 0
        self.users = {}
        self.roles = {}
        self.deleted = []
        self.fail_role = False
        self.password_was_temporary = False

    def user_count(self):
        return self.count

    def exact_users(self, username):
        return [user for user in self.users.values() if user["username"] == username]

    def exact_email_users(self, email):
        return [user for user in self.users.values() if user.get("email") == email]

    def realm_role(self, name):
        return {"id": "role-id", "name": name}

    def create_user(self, profile):
        self.users["user-id"] = {"id": "user-id", "totp": False, **profile}
        return "user-id"

    def reset_password(self, user_id, password):
        self.password_was_temporary = bool(password)

    def assign_realm_role(self, user_id, role):
        if self.fail_role:
            raise RuntimeError("synthetic role failure")
        self.roles[user_id] = [role]

    def update_user(self, user_id, profile):
        self.users[user_id].update(profile)

    def user(self, user_id):
        return self.users[user_id]

    def realm_roles(self, user_id):
        return self.roles.get(user_id, [])

    def delete_user(self, user_id):
        self.deleted.append(user_id)
        self.users.pop(user_id, None)


class FirstUserContract(unittest.TestCase):
    def test_first_user_is_disabled_until_password_role_and_actions_are_set(self):
        api = FakeAdmin()
        MODULE.provision_user(api, PROFILE, "temporary-password")
        user = api.users["user-id"]
        self.assertTrue(api.password_was_temporary)
        self.assertTrue(user["enabled"])
        self.assertFalse(user["emailVerified"])
        self.assertFalse(user["totp"])
        self.assertEqual(set(user["requiredActions"]), MODULE.REQUIRED_ACTIONS)
        self.assertIn(MODULE.ROLE, {role["name"] for role in api.roles["user-id"]})

    def test_partial_user_is_deleted_when_role_assignment_fails(self):
        api = FakeAdmin()
        api.fail_role = True
        with self.assertRaisesRegex(RuntimeError, "new identity was removed"):
            MODULE.provision_user(api, PROFILE, "temporary-password")
        self.assertEqual(api.deleted, ["user-id"])
        self.assertEqual(api.users, {})

    def test_nonempty_realm_is_refused_before_mutation(self):
        api = FakeAdmin()
        api.count = 1
        with self.assertRaisesRegex(RuntimeError, "realm is not empty"):
            MODULE.provision_user(api, PROFILE, "temporary-password")
        self.assertEqual(api.users, {})

    def test_verification_requires_totp_completed_actions_and_role(self):
        api = FakeAdmin()
        MODULE.provision_user(api, PROFILE, "temporary-password")
        with self.assertRaisesRegex(RuntimeError, "TOTP is not active"):
            MODULE.verify_user(api, PROFILE["username"])
        api.users["user-id"].update(totp=True, requiredActions=[])
        MODULE.verify_user(api, PROFILE["username"])

    def test_pre_login_email_correction_preserves_role_and_actions(self):
        api = FakeAdmin()
        MODULE.provision_user(api, PROFILE, "temporary-password")
        api.count = 1
        MODULE.correct_email(api, PROFILE["username"], "corrected@example.com")
        user = api.users["user-id"]
        self.assertEqual(user["email"], "corrected@example.com")
        self.assertFalse(user["emailVerified"])
        self.assertTrue(user["enabled"])
        self.assertFalse(user["totp"])
        self.assertEqual(set(user["requiredActions"]), MODULE.REQUIRED_ACTIONS)
        self.assertIn(MODULE.ROLE, {role["name"] for role in api.roles["user-id"]})

    def test_email_correction_is_refused_after_totp_setup(self):
        api = FakeAdmin()
        MODULE.provision_user(api, PROFILE, "temporary-password")
        api.count = 1
        api.users["user-id"].update(totp=True, requiredActions=[])
        with self.assertRaisesRegex(RuntimeError, "initial onboarding state"):
            MODULE.correct_email(api, PROFILE["username"], "corrected@example.com")
        self.assertEqual(api.users["user-id"]["email"], PROFILE["email"])

    def test_email_correction_is_refused_when_initial_actions_differ(self):
        api = FakeAdmin()
        MODULE.provision_user(api, PROFILE, "temporary-password")
        api.count = 1
        api.users["user-id"]["requiredActions"].append("VERIFY_EMAIL")
        with self.assertRaisesRegex(RuntimeError, "initial onboarding state"):
            MODULE.correct_email(api, PROFILE["username"], "corrected@example.com")
        self.assertEqual(api.users["user-id"]["email"], PROFILE["email"])

    def test_identity_validation_refuses_bootstrap_or_ambiguous_values(self):
        with self.assertRaisesRegex(RuntimeError, "distinct"):
            MODULE.validate_profile(PROFILE, PROFILE["username"])
        invalid = {**PROFILE, "username": "Pilot User"}
        with self.assertRaisesRegex(RuntimeError, "username"):
            MODULE.validate_profile(invalid, "bootstrap")
        invalid = {**PROFILE, "email": "not-an-email"}
        with self.assertRaisesRegex(RuntimeError, "email"):
            MODULE.validate_profile(invalid, "bootstrap")


if __name__ == "__main__":
    unittest.main(verbosity=2)
