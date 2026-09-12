"""Static contract for the user-free production Keycloak realm bootstrap."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
REALM_PATH = ROOT / "infrastructure/keycloak/production/nevolium-realm.json"
COMPOSE_PATH = ROOT / "compose.production.yaml"


class KeycloakProductionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.realm = json.loads(REALM_PATH.read_text(encoding="utf-8"))
        cls.compose = COMPOSE_PATH.read_text(encoding="utf-8")

    def test_realm_has_no_users_and_requires_external_tls(self):
        self.assertNotIn("users", self.realm)
        self.assertEqual(self.realm["realm"], "${KEYCLOAK_REALM}")
        self.assertEqual(self.realm["sslRequired"], "external")
        self.assertFalse(self.realm["registrationAllowed"])
        self.assertTrue(self.realm["bruteForceProtected"])

    def test_web_client_is_public_pkce_and_exact_origin(self):
        self.assertEqual(len(self.realm["clients"]), 1)
        client = self.realm["clients"][0]
        self.assertEqual(client["clientId"], "${KEYCLOAK_CLIENT_ID}")
        self.assertTrue(client["publicClient"])
        self.assertTrue(client["standardFlowEnabled"])
        self.assertFalse(client["implicitFlowEnabled"])
        self.assertFalse(client["directAccessGrantsEnabled"])
        self.assertFalse(client["serviceAccountsEnabled"])
        self.assertEqual(client["redirectUris"], ["${NEVOLIUM_CORS_ORIGINS}/*"])
        self.assertEqual(client["webOrigins"], ["${NEVOLIUM_CORS_ORIGINS}"])
        self.assertEqual(client["attributes"], {"pkce.code.challenge.method": "S256"})

        self.assertEqual(len(client["protocolMappers"]), 1)
        mapper = client["protocolMappers"][0]
        self.assertEqual(mapper["protocolMapper"], "oidc-audience-mapper")
        self.assertEqual(mapper["config"]["included.custom.audience"], "nevolium-core")
        self.assertEqual(mapper["config"]["access.token.claim"], "true")
        self.assertEqual(mapper["config"]["id.token.claim"], "false")

    def test_production_compose_imports_only_the_production_realm(self):
        required = (
            "- --import-realm",
            "NEVOLIUM_CORS_ORIGINS: ${NEVOLIUM_CORS_ORIGINS}",
            "KEYCLOAK_REALM: ${KEYCLOAK_REALM}",
            "KEYCLOAK_CLIENT_ID: ${KEYCLOAK_CLIENT_ID}",
            "./infrastructure/keycloak/production/nevolium-realm.json:/opt/keycloak/data/import/nevolium-realm.json:ro",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.compose)
        self.assertNotIn("./infrastructure/keycloak/nevolium-realm.json", self.compose)


if __name__ == "__main__":
    unittest.main(verbosity=2)
