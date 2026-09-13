"""Static contract for the bounded production TLS ingress."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
CADDYFILE = ROOT / "infrastructure/caddy/Caddyfile"


def site_block(text: str, hostname: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(hostname)} \{{\n(.*?)(?=^\}}$)", text
    )
    if match is None:
        raise AssertionError(f"missing site block for {hostname}")
    return match.group(1)


class IngressContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CADDYFILE.read_text(encoding="utf-8")

    def test_only_expected_public_names_and_loopback_upstreams(self):
        expected = {
            "app.nevolium.com": "127.0.0.1:5173",
            "api.nevolium.com": "127.0.0.1:8000",
            "auth.nevolium.com": "127.0.0.1:8081",
        }
        site_names = set(
            re.findall(r"(?m)^([a-z0-9.-]+\.nevolium\.com) \{$", self.config)
        )
        self.assertEqual(site_names, set(expected))
        self.assertNotIn("*.", self.config)

        for hostname, upstream in expected.items():
            with self.subTest(hostname=hostname):
                block = site_block(self.config, hostname)
                self.assertEqual(
                    re.findall(r"(?m)^\s*reverse_proxy ([^\s]+)$", block),
                    [upstream],
                )

    def test_api_is_allowlisted_and_every_other_path_is_denied(self):
        block = site_block(self.config, "api.nevolium.com")
        self.assertIn("@public_api path /v1 /v1/*", block)
        self.assertRegex(
            block,
            r"(?s)handle @public_api \{.*reverse_proxy 127\.0\.0\.1:8000.*\}",
        )
        self.assertRegex(block, r"(?s)handle \{\s*respond 404\s*\}")
        self.assertLess(block.index("handle @public_api"), block.index("respond 404"))

    def test_public_tls_and_safe_logging_defaults_are_preserved(self):
        for forbidden in (
            "http://",
            "auto_https off",
            "tls internal",
            "skip_verify",
            "log {",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.config)
        self.assertIn("Strict-Transport-Security \"max-age=31536000\"", self.config)
        self.assertIn("admin 127.0.0.1:2019", self.config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
