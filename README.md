# OCI Cloud Guard email notifications

Send email when Cloud Guard detects security problems in selected targets.
Set all automation inputs in **`terraform/cloudguard.auto.tfvars.json`**:
the reporting region, OCI profile, notification compartment, email recipients
and event filters. Step 5 explains how to create and fill in this file.

```text
Cloud Guard detector -> problem -> Cloud Event responder
  -> OCI Events rule -> Notifications topic -> confirmed email subscribers
```

The stack creates one Events rule, one Notifications topic and one subscription
per distinct email address. Cloud Guard enablement, targets, recipes and IAM
policies are configured separately. No Function or subnet is needed.

## 1. Prepare the deployment machine and OCI access

Install Python 3.10+, Terraform 1.3+ and OCI CLI. No Python packages are needed.
Run all commands below from this project's root directory.

```powershell
python --version
terraform version
oci --version
```

Use a working OCI API-key profile. If you need to create one, run
`oci setup config` and upload the generated public API key to your OCI user.

Ask your tenancy administrator to grant the following deployment permissions.
Replace `<deployment-group>` with your OCI group and
`<notification-compartment-ocid>` with the compartment OCID where the
Notifications topic and subscriptions will be created:

```text
Allow group <deployment-group> to read cloud-guard-config in tenancy
Allow group <deployment-group> to manage cloudevents-rules in tenancy
Allow group <deployment-group> to manage ons-topics in compartment id <notification-compartment-ocid>
Allow group <deployment-group> to manage ons-subscriptions in compartment id <notification-compartment-ocid>
```

If storing notifications at tenancy root, use `in tenancy` in the last two
statements. Cloud Guard administration and test-resource creation require
separate permissions. This stack does not create IAM policies.

## 2. Check Cloud Guard and its reporting region

1. Open **Identity & Security -> Cloud Guard** in the OCI Console.
2. If the Overview already shows findings, Cloud Guard is enabled. Skip enablement.
3. If disabled, an administrator must enable it in a supported paid tenancy:
   create the service policies offered by the wizard, select a reporting region,
   choose compartments to monitor and attach configuration/activity detectors.
4. Open **Cloud Guard -> Configuration -> Settings**. Record **Reporting region**.
5. Switch the Console to that region for the remaining Cloud Guard setup.

Use this reporting region for the automation's `region`. For example, set
`us-ashburn-1` if reporting is in Ashburn, even when resources are in Frankfurt.
The Events rule and Notifications topic are created in the reporting region.
Do not disable/re-enable Cloud Guard to change regions: this deletes its
customizations and problem history.

[Oracle enablement guide](https://docs.oracle.com/en-us/iaas/Content/cloud-guard/using/part-start.htm)

## 3. Choose or create a Cloud Guard target

A target defines the compartment and descendants Cloud Guard monitors.

1. Open **Cloud Guard -> Configuration -> Targets**.
2. Select the relevant compartment. If no targets appear, select tenancy root
   and include children to find targets higher in the hierarchy.
3. Reuse an existing target if its detectors and responder meet the requirement.
   Do not replace shared or governed recipes just for a test.
4. For a dedicated test, select **Create target**, name it
   `cloudguard-notifications-test` and select your test compartment.
5. In **Configuration -> Posture and threat monitoring recipes**, select
   **OCI Configuration Detector Recipe**. This is sufficient for the bucket test.
   Add an Activity detector too if activity findings are required.
6. Leave Instance Security and Container Security unselected for this basic test.
7. Review the name, compartment and detector selection, then create the target.

A child target changes inherited monitoring settings for that compartment;
coordinate with the administrator when existing governance applies.

From the target's **Details** tab, copy its OCID. It must start with
**`ocid1.cloudguardtarget.`**, not `ocid1.cloudguardresponderrecipe.`.

[Oracle target guide](https://docs.oracle.com/en-us/iaas/Content/cloud-guard/using/targets-create.htm)

## 4. Enable automatic Cloud Event emission

If the target already has Cloud Event enabled with automatic execution, keep
that configuration. Otherwise, create a dedicated notification responder:

1. Open **Cloud Guard -> Recipes -> Responder Recipes**.
2. Select tenancy root, find **OCI Responder Recipe (Oracle managed)** and
   choose **Clone**.
3. In the clone form, set **Recipe compartment** to root (source), select the
   Oracle-managed recipe, and name the copy `cloudguard-notification-responder`.
4. Set **Compartment**, below Description, to your test compartment (destination).
5. Clone it and open **Responder rules**. Keep **Cloud Event (`EVENT`) Enabled**.
   In this dedicated notification-only recipe, disable every other rule,
   including **Make Bucket Private**.
6. Return to **Targets -> your target -> Configuration -> Responder recipes**.
7. Select **Add recipes**, choose the destination compartment and attach the clone.
8. Open the attached recipe **through the target**, then edit **Cloud Event**.
9. Select **Execute automatically**, tick **Confirm execute automatically**,
   leave conditional groups empty for the test, and save.

Cloud Event publishes problem details and needs no additional responder IAM
policies. The dialog's resource-modification warning is generic: this rule
emits events without changing the affected resource. You don't need to turn
on automatic remediation.

[Oracle responder reference](https://docs.oracle.com/en-us/iaas/Content/cloud-guard/using/respond-recipes-reference.htm)

## 5. Configure terraform/cloudguard.auto.tfvars.json

Create the file once, only if it does not already exist:

```powershell
python -c "from shutil import copyfile; copyfile('terraform/cloudguard.example.tfvars.json', 'terraform/cloudguard.auto.tfvars.json')"
```

Edit only **`terraform/cloudguard.auto.tfvars.json`**. Replace all `CHANGE HERE`
values. For the dedicated test, set `target_ids` to the target OCID from step 3.

`scripts/deploy_stack.py` and `scripts/verify_stack.py` read the tenancy OCID
from the selected profile in `~/.oci/config` (`%USERPROFILE%\.oci\config` on
Windows). Do not add `tenancy_id` to the JSON.

| Setting | What to enter |
| --- | --- |
| `region` | Cloud Guard reporting region, for example `us-ashburn-1`. |
| `oci_profile` | Profile name from your OCI config, normally `DEFAULT`. |
| `notification_compartment_id` | Compartment OCID where the topic and subscriptions will live. A tenancy OCID uses root. This does not select what Cloud Guard monitors. |
| `events_compartment_id` | Keep `null` initially: create the Events rule at tenancy root, covering descendants. |
| `name_prefix` | Keep the default or choose a unique resource naming prefix. |
| `email_recipients` | Your real email addresses; each recipient must confirm the subscription. |
| `problem_event_types` | Keep `["com.oraclecloud.cloudguard.problemdetected"]` for new findings. |
| `risk_levels` | Keep `[]` for all severities initially. |
| `target_ids` | `["<your target OCID>"]` limits emails to that target. `[]` includes all targets within the Events scope. |
| `is_enabled` | Keep `true`. `false` pauses the Events rule and action. |

For multiple targets, separate the quoted OCIDs with commas inside the array:

```json
"target_ids": [
  "<first target OCID>",
  "<second target OCID>"
]
```

Do not add a comma after the last OCID. A problem from any listed target can match.

For multiple email recipients, separate the quoted addresses with commas:

```json
"email_recipients": [
  "person@example.com",
  "security@example.com"
]
```

Do not add a comma after the last address. Each recipient must confirm their
own subscription.

To send every listed recipient notifications for new problems across all monitored
targets in your tenancy, use these settings in the same JSON file:

```json
{
  "events_compartment_id": null,
  "target_ids": [],
  "risk_levels": [],
  "problem_event_types": ["com.oraclecloud.cloudguard.problemdetected"]
}
```

This is a configuration excerpt; keep the other settings in your file.
Every relevant target must have **Cloud Event enabled and set to Execute
Automatically**, as described in step 4. The script does not configure responders
on other targets. All confirmed recipients receive the same matching events;
there are no separate filters per recipient. Existing findings are not replayed.
Run plan and apply again after changing these settings.

No Python or Terraform source edits are needed. Keep your configuration file, credentials
and Terraform state private. Terraform generates its provider lock file locally;
it is excluded from this repository. Use separate
project/state directories for different tenancies: changing the profile does
not select a separate Terraform state.

## 6. Plan and deploy

Run both commands below from the **repository root directory**: the folder
containing `README.md`, `scripts/` and `terraform/`.

**Step 1: Preview the changes.** Run:
It runs `terraform plan` through the deployment script and shows what will be
created, changed or deleted without deploying resources.

```powershell
python scripts/deploy_stack.py plan --config terraform/cloudguard.auto.tfvars.json
```

For one recipient on a new stack, expect **3 to add, 0 to change, 0 to destroy**:
topic, email subscription and Events rule. Check the target OCID and event type
in `event_condition`. Resolve errors before applying.

**Step 2: Deploy the resources.** After reviewing the plan, run:

```powershell
python scripts/deploy_stack.py apply --config terraform/cloudguard.auto.tfvars.json
```

This runs `terraform apply` through the deployment script and creates the
Notifications topic, email subscriptions and Events rule.

The script runs init and validate before plan/apply. Apply calculates a fresh
plan and uses `-auto-approve`; it does not apply a previously saved plan.
Use the script so Terraform receives the tenancy OCID from your profile.
`scripts/deploy_stack.py` and `scripts/verify_stack.py` use `oci_profile` from
`terraform/cloudguard.auto.tfvars.json`. Optional `--profile MY_PROFILE`
overrides it; use the same profile for deployment and verification.

## 7. Confirm subscriptions, then verify

1. Open the OCI confirmation email and click **Confirm Subscription**.
   Every recipient must do this.
2. In the reporting region, open **Notifications -> your topic -> Subscriptions**
   and check that each subscription is **Active**.
3. Run:

```powershell
python scripts/verify_stack.py --config terraform/cloudguard.auto.tfvars.json
```

This makes real, read-only OCI calls. It checks Cloud Guard enablement/reporting
region, the Events rule/action/filter and active subscriptions. Before email
confirmation, it reports a pending subscription as a failure.

A pass proves configuration readiness. It does not check detector/responder
settings or prove inbox delivery. Apply JSON changes before verifying: the
checks compare live resources with Terraform outputs.

## 8. Test a real finding and email

Run this after deployment and subscription confirmation:

1. In the target's attached Configuration Detector recipe, confirm **Bucket is
   public** is enabled, with no conditions excluding your test resource.
2. In the resource region (Frankfurt is fine), open **Storage -> Object Storage ->
   Buckets** and select the monitored test compartment.
3. Create a new empty bucket, such as `cloudguard-email-test`, and change its
   **Visibility** to **Public**. Keep it empty. If a policy blocks public access,
   use another administrator-approved finding instead of weakening the policy.
4. In the reporting region, open **Cloud Guard -> Alerts -> Problems**.
5. Select the test compartment, include children, clear search text and the
   **Last detected** date filter, and look for **Bucket is public**.
6. Open the finding, confirm its bucket name/target, and check **Responder
   activity** for **Cloud Event: Succeeded**.
7. Confirm every recipient receives an email naming that bucket/problem.
8. Restore the bucket to **Private**, then delete it.

Detection and email delivery are asynchronous. This automation does not control
scan timing; do not assume detection within a fixed number of minutes.
The email contains OCI's native JSON, including the resource, severity, target
and recommendation. Other enabled detectors can also produce key or policy
notifications for the same target.

To test delivery with an existing real finding, manually trigger only its
Cloud Event responder. Replace the placeholders before running:

```powershell
oci cloud-guard problem trigger-responder --region <reporting-region> --profile <profile-name> --problem-id <problem-ocid> --responder-rule-id EVENT
```

This emits a real event without remediating the resource. It tests delivery for
an existing finding; the bucket test also proves fresh automatic detection.
Deploying the stack does not replay old findings. Publishing directly to the
topic tests Notifications only.

## 9. Troubleshoot the missing stage

| Symptom | Check |
| --- | --- |
| No bucket problem | Bucket visibility/compartment, target's monitored compartment, effective detector/conditions, Problems filters and detection delay. |
| Problem exists, no Cloud Event success | Attached responder recipe, Cloud Event enabled and automatic execution at target level. |
| Cloud Event succeeded, no email | Event occurred after rule creation; correct reporting region; matching target/event filters; enabled ONS action; active subscription. |
| Unsure whether OCI transmitted it | Open the Notifications topic metrics: check `PublishedMessagesCount`, `DeliveredMessagesCount` and `FailedMessagesCount` around the event time. Delivery means transmission to the email endpoint, not inbox placement. |
| OCI reports delivery | Check inbox, junk and corporate quarantine; allow for mail processing delay. |
| Invalid `target_ids` | Use `ocid1.cloudguardtarget.`, not a recipe OCID. |

For broader scope, check the Cloud Event prerequisite for every intended target.
Restrict severity only after inspecting a real payload. Supported severities are
`CRITICAL`, `HIGH`, `MEDIUM`, `LOW` and `MINOR`.

Optional lifecycle types are `com.oraclecloud.cloudguard.problemdismissed` and
`com.oraclecloud.cloudguard.problemremediated`. Verify actual lifecycle payloads
before filtering. Filters use `data.additionalDetails.targetId` and `riskLevel`;
values within a field are ORed, different fields are ANDed, and missing filtered
fields prevent matching.

This stack forwards problem events, with no custom email formatting, scheduled
reminders, historical scan or application deduplication. Exactly one email per
problem is not guaranteed.

## 10. Remove the notification stack

```powershell
python scripts/deploy_stack.py destroy --config terraform/cloudguard.auto.tfvars.json
```

This removes the topic, subscriptions and Events rule. Separately configured
Cloud Guard targets, recipes, IAM policies and test resources remain.
`recreate` destroys then applies; recipients must confirm subscriptions again,
and events during the gap are not replayed.
