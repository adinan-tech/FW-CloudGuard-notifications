"""Plan, deploy, destroy or recreate the Cloud Guard notification stack."""

import argparse
import configparser
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "terraform"


def load_settings(config: Path) -> dict:
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    if not isinstance(settings, dict):
        raise ValueError("configuration must be a JSON object")
    for key in ("region", "notification_compartment_id", "email_recipients"):
        if not settings.get(key):
            raise ValueError(f"missing configuration: {key}")
    if "CHANGE HERE" in json.dumps(settings):
        raise ValueError("replace all CHANGE HERE placeholders before deployment")
    return settings


def profile_tenancy(profile: str, config_file: Path | None = None) -> str:
    config_file = config_file or Path.home() / ".oci" / "config"
    # Disable interpolation: OCI configuration values are literal strings.
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with config_file.open(encoding="utf-8-sig") as stream:
            parser.read_file(stream)
    except (OSError, configparser.Error) as error:
        raise ValueError(f"Cannot read OCI configuration at {config_file}.") from error
    if profile not in parser:
        raise ValueError(f"OCI profile '{profile}' was not found in {config_file}.")
    tenancy = parser[profile].get("tenancy", "").strip()
    if not re.fullmatch(r"ocid1\.tenancy\.[^<>\s]+", tenancy):
        raise ValueError(f"OCI profile '{profile}' must contain a valid tenancy OCID.")
    return tenancy


def resolve_settings(settings: dict, profile: str | None = None) -> dict:
    settings = dict(settings)
    selected_profile = profile or settings.get("oci_profile", "DEFAULT")
    tenancy = profile_tenancy(selected_profile)
    if settings.get("tenancy_id") not in (None, tenancy):
        raise ValueError("Remove tenancy_id from the customer JSON; the selected OCI profile supplies it.")
    settings.update(oci_profile=selected_profile, tenancy_id=tenancy)
    return settings


def command(args: list[str]) -> None:
    # Inherit the console so Terraform diagnostics remain visible while it runs.
    subprocess.run(args, cwd=ROOT, timeout=1800, check=True)


def deploy(action: str, config: Path, profile: str | None = None) -> None:
    settings = resolve_settings(load_settings(config), profile)
    base = ["terraform", f"-chdir={TERRAFORM}"]
    command(base + ["init", "-input=false"])
    command(base + ["validate"])
    variables = [f"-var-file={config}", f"-var=oci_profile={settings['oci_profile']}",
                 f"-var=tenancy_id={settings['tenancy_id']}"]

    def run(operation: str) -> None:
        arguments = base + [operation, "-input=false"] + variables
        if operation in ("apply", "destroy"):
            arguments.append("-auto-approve")
        command(arguments)

    if action == "recreate":
        run("destroy")
        run("apply")
    else:
        run(action)
    if action in ("apply", "recreate"):
        print("Confirm each email subscription, check the Cloud Event responder, then run verify_stack.py.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "apply", "destroy", "recreate"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--profile", help="Override oci_profile for Terraform")
    args = parser.parse_args()
    try:
        deploy(args.action, args.config.resolve(), args.profile)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"stack deployment failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
