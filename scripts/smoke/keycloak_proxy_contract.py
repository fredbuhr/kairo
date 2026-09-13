"""Contract for safe Keycloak trusted-proxy configuration."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "configure_keycloak_proxy",
    ROOT / "scripts/ops/configure_keycloak_proxy.py",
)
proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proxy)


class KeycloakProxyContract(unittest.TestCase):
    def test_only_an_exact_private_ipv4_is_accepted(self):
        self.assertEqual(proxy.exact_private_ipv4("172.20.0.1"), "172.20.0.1/32")
        for invalid in ("", "8.8.8.8", "0.0.0.0", "172.20.0.0/16", "::1"):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, RuntimeError)):
                proxy.exact_private_ipv4(invalid)

    def test_placeholder_is_replaced_without_touching_other_values(self):
        original = (
            "FIRST_SECRET=preserved\n"
            "KEYCLOAK_PROXY_TRUSTED_ADDRESSES=CHANGE_ME_PROXY_ADDRESS\n"
            "LAST_SECRET=also-preserved\n"
        )
        rendered, changed = proxy.render_env(original, "172.20.0.1/32")
        self.assertTrue(changed)
        self.assertEqual(
            rendered,
            original.replace("CHANGE_ME_PROXY_ADDRESS", "172.20.0.1/32"),
        )
        self.assertEqual(proxy.render_env(rendered, "172.20.0.1/32"), (rendered, False))

    def test_existing_missing_or_duplicate_assignment_is_refused(self):
        invalid = (
            "OTHER=value\n",
            "KEYCLOAK_PROXY_TRUSTED_ADDRESSES=172.21.0.1/32\n",
            "KEYCLOAK_PROXY_TRUSTED_ADDRESSES=CHANGE_ME_PROXY_ADDRESS\n"
            "KEYCLOAK_PROXY_TRUSTED_ADDRESSES=CHANGE_ME_PROXY_ADDRESS\n",
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                proxy.render_env(text, "172.20.0.1/32")


if __name__ == "__main__":
    unittest.main(verbosity=2)
