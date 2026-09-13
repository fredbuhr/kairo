"""Static and behavioral contract for monitored OpenBao token renewal."""

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "renew_openbao_token",
    ROOT / "scripts/ops/renew_openbao_token.py",
)
renewal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renewal)


class OpenBaoRenewal(unittest.TestCase):
    def metadata(self):
        return {
            "accessor": "accessor-fixture",
            "display_name": "nevolium-core",
            "period_seconds": 604800,
            "created_at": "2026-09-12T00:00:00+00:00",
        }

    def lookup(self, **changes):
        data = {
            "accessor": "accessor-fixture",
            "policies": ["nevolium-core"],
            "period": 604800,
            "ttl": 604799,
            "renewable": True,
            "orphan": True,
        }
        data.update(changes)
        return json.dumps({"data": data})

    def test_token_and_metadata_are_exact(self):
        token = "s." + "a" * 24
        self.assertEqual(renewal.env_token("OPENBAO_TOKEN=" + token), token)
        self.assertEqual(
            renewal.workload_metadata(json.dumps(self.metadata()))["accessor"],
            "accessor-fixture",
        )
        for text in (
            "",
            "OPENBAO_TOKEN=change_me",
            "OPENBAO_TOKEN=" + token + "\nOPENBAO_TOKEN=" + token,
        ):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                renewal.env_token(text)

    def test_lookup_requires_bound_identity_and_fresh_period(self):
        self.assertEqual(
            renewal.validate_lookup(self.lookup(), self.metadata(), 518400),
            604799,
        )
        invalid = (
            {"accessor": "other"},
            {"policies": ["default", "nevolium-core"]},
            {"period": 3600},
            {"ttl": 518399},
            {"renewable": False},
            {"orphan": False},
        )
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                renewal.validate_lookup(
                    self.lookup(**change), self.metadata(), 518400
                )

    def test_systemd_timer_is_daily_persistent_and_hardened(self):
        unit = (ROOT / "infrastructure/systemd/nevolium-openbao-renew.service").read_text()
        timer = (ROOT / "infrastructure/systemd/nevolium-openbao-renew.timer").read_text()
        for required in (
            "User=root",
            "NoNewPrivileges=yes",
            "ProtectSystem=strict",
            "CapabilityBoundingSet=CAP_DAC_READ_SEARCH",
            "RestrictAddressFamilies=AF_UNIX",
            "ReadOnlyPaths=/etc/nevolium /opt/nevolium/source",
        ):
            self.assertIn(required, unit)
        self.assertIn("OnCalendar=*-*-* 03:17:00 UTC", timer)
        self.assertIn("RandomizedDelaySec=30min", timer)
        self.assertIn("Persistent=true", timer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
