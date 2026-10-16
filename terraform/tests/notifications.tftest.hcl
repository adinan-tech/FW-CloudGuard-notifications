mock_provider "oci" {}

override_data {
  target = data.oci_cloud_guard_cloud_guard_configuration.existing
  values = {
    status           = "ENABLED"
    reporting_region = "eu-frankfurt-1"
  }
}

variables {
  region                      = "eu-frankfurt-1"
  tenancy_id                  = "ocid1.tenancy.oc1..test"
  notification_compartment_id = "ocid1.compartment.oc1..test"
  email_recipients            = ["security@example.com"]
}

run "default_detection" {
  command = plan
  assert {
    condition     = jsonencode(output.event_condition) == jsonencode({ eventType = ["com.oraclecloud.cloudguard.problemdetected"] })
    error_message = "Default must forward detected events without empty payload filters."
  }
  assert {
    condition     = oci_events_rule.cloudguard.compartment_id == var.tenancy_id
    error_message = "Default Events scope must include the tenancy."
  }
}

run "filtered_lifecycle" {
  command = plan
  variables {
    risk_levels           = ["HIGH", "CRITICAL"]
    target_ids            = ["ocid1.cloudguardtarget.oc1..test"]
    problem_event_types   = ["com.oraclecloud.cloudguard.problemdetected", "com.oraclecloud.cloudguard.problemremediated"]
    events_compartment_id = "ocid1.compartment.oc1..scope"
  }
  assert {
    condition     = jsonencode(output.event_condition.data.additionalDetails.riskLevel) == jsonencode(["CRITICAL", "HIGH"]) && jsonencode(output.event_condition.data.additionalDetails.targetId) == jsonencode(["ocid1.cloudguardtarget.oc1..test"])
    error_message = "Filters must use additionalDetails nesting and sorted values."
  }
  assert {
    condition     = length(output.event_condition.eventType) == 2 && !can(output.event_condition.data.additionalDetails.status)
    error_message = "Lifecycle filters must not force status OPEN."
  }
  assert {
    condition     = oci_events_rule.cloudguard.compartment_id == var.events_compartment_id
    error_message = "Explicit Events scope must be respected."
  }
}

run "wrong_region" {
  command = plan
  variables {
    region = "us-ashburn-1"
  }
  expect_failures = [oci_ons_notification_topic.cloudguard]
}

run "disabled_cloudguard" {
  command = plan
  override_data {
    target = data.oci_cloud_guard_cloud_guard_configuration.existing
    values = {
      status           = "DISABLED"
      reporting_region = "eu-frankfurt-1"
    }
  }
  expect_failures = [oci_ons_notification_topic.cloudguard]
}
