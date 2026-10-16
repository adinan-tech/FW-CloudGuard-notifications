import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from deploy_stack import deploy
from verify_stack import verify


class ScriptsTest(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "region": "eu-frankfurt-1", "tenancy_id": "ocid1.tenancy.oc1..test",
            "notification_compartment_id": "ocid1.compartment.oc1..test",
            "email_recipients": ["security@example.com"],
        }
        self.condition = {"eventType": ["com.oraclecloud.cloudguard.problemdetected"]}
        self.outputs = {key: {"value": value} for key, value in {
            "events_rule_id": "rule", "topic_id": "topic", "event_condition": self.condition,
            "subscription_ids": {"security@example.com": "subscription"},
        }.items()}
        self.responses = {
            "cloud-guard": {"status": "ENABLED", "reporting-region": self.settings["region"]},
            "events": {"lifecycle-state": "ACTIVE", "is-enabled": True,
                       "condition": json.dumps(self.condition), "actions": {"actions": [
                           {"action-type": "ONS", "topic-id": "topic", "is-enabled": True}]}},
            "ons": {"lifecycle-state": "ACTIVE", "topic-id": "topic", "endpoint": "security@example.com"},
        }

    def check(self):
        return verify(self.settings, self.outputs, lambda args: {"data": self.responses[args[0]]})

    def test_active_stack(self):
        self.assertEqual(self.check(), [])

    def test_pending_email_and_disabled_action(self):
        self.responses["ons"]["lifecycle-state"] = "PENDING"
        self.responses["events"]["actions"]["actions"][0]["is-enabled"] = False
        failures = self.check()
        self.assertEqual(len(failures), 2)
        self.assertTrue(any("not ACTIVE" in value for value in failures))

    def test_wrong_region_and_filter_drift(self):
        self.responses["cloud-guard"]["reporting-region"] = "us-ashburn-1"
        self.responses["events"]["condition"] = "{}"
        self.assertEqual(len(self.check()), 2)

    def test_profile_applies_to_terraform(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            config.write_text(json.dumps(self.settings), encoding="utf-8")
            with patch("deploy_stack.profile_tenancy", return_value=self.settings["tenancy_id"]), \
                    patch("deploy_stack.command") as command:
                deploy("plan", config, "CUSTOMER")
            arguments = command.call_args_list[-1].args[0]
            self.assertIn("plan", arguments)
            self.assertIn("-var=oci_profile=CUSTOMER", arguments)
            self.assertIn(f"-var=tenancy_id={self.settings['tenancy_id']}", arguments)
            self.assertNotIn("-auto-approve", arguments)

    def test_placeholders_fail_before_any_command(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            self.settings["region"] = "CHANGE HERE"
            config.write_text(json.dumps(self.settings), encoding="utf-8")
            with patch("deploy_stack.command") as command:
                with self.assertRaises(ValueError):
                    deploy("apply", config)
                command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
