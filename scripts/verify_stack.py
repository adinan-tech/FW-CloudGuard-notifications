"""Read-only OCI checks; these do not prove delivery of a Cloud Guard event."""

import argparse
import json
from pathlib import Path
import subprocess

from deploy_stack import TERRAFORM, load_settings, resolve_settings


def read_json(args: list[str]) -> dict:
    result = subprocess.run(args, text=True, capture_output=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def verify(settings: dict, outputs: dict, request) -> list[str]:
    failures = []
    config = request(["cloud-guard", "configuration", "get", "--compartment-id", settings["tenancy_id"]])["data"]
    if config.get("status") != "ENABLED" or config.get("reporting-region") != settings["region"]:
        failures.append("Cloud Guard is disabled or the reporting region does not match.")
    rule = request(["events", "rule", "get", "--rule-id", outputs["events_rule_id"]["value"]])["data"]
    if rule.get("lifecycle-state") != "ACTIVE" or not rule.get("is-enabled"):
        failures.append("Events rule is not active and enabled.")
    expected_topic = outputs["topic_id"]["value"]
    actions = rule.get("actions", {}).get("actions", [])
    if not any(action.get("action-type") == "ONS" and action.get("topic-id") == expected_topic
               and action.get("is-enabled") for action in actions):
        failures.append("No enabled ONS action points to the deployed topic.")
    if json.loads(rule["condition"]) != outputs["event_condition"]["value"]:
        failures.append("The deployed Events filter differs from Terraform outputs.")
    for email, subscription_id in outputs["subscription_ids"]["value"].items():
        subscription = request(["ons", "subscription", "get", "--subscription-id", subscription_id])["data"]
        if subscription.get("lifecycle-state") != "ACTIVE":
            failures.append(f"Email subscription is not ACTIVE: {email}")
        if subscription.get("topic-id") != expected_topic or subscription.get("endpoint") != email:
            failures.append(f"Email subscription endpoint/topic differs: {email}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--profile", help="Override the configured OCI profile")
    args = parser.parse_args()
    try:
        settings = resolve_settings(load_settings(args.config), args.profile)
        outputs = read_json(["terraform", f"-chdir={TERRAFORM}", "output", "-json"])
        prefix = ["oci", "--config-file", str(Path.home() / ".oci" / "config"),
                  "--region", settings["region"], "--profile",
                  settings["oci_profile"], "--output", "json"]
        failures = verify(settings, outputs, lambda options: read_json(prefix + options))
        for failure in failures:
            print(f"FAIL: {failure}")
        if failures:
            return 1
        print("Configuration, Events rule/action/filter and email subscriptions passed read-only checks.")
        print("Still verify Cloud Event responder configuration and a real problem-to-email delivery.")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"verification failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
