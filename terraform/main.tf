locals {
  additional_details = merge(
    length(var.risk_levels) == 0 ? {} : { riskLevel = sort(tolist(var.risk_levels)) },
    length(var.target_ids) == 0 ? {} : { targetId = sort(tolist(var.target_ids)) }
  )
  event_condition = merge(
    { eventType = sort(tolist(var.problem_event_types)) },
    length(local.additional_details) == 0 ? {} : { data = { additionalDetails = local.additional_details } }
  )
}

# Existing security posture is owned by the tenancy administrators, not this stack.
data "oci_cloud_guard_cloud_guard_configuration" "existing" {
  compartment_id = var.tenancy_id
}

resource "oci_ons_notification_topic" "cloudguard" {
  compartment_id = var.notification_compartment_id
  name           = "${var.name_prefix}_alerts"
  description    = "Cloud Guard problem email notifications"

  lifecycle {
    precondition {
      condition     = data.oci_cloud_guard_cloud_guard_configuration.existing.status == "ENABLED"
      error_message = "Cloud Guard must already be enabled by the tenancy administrator."
    }
    precondition {
      condition     = data.oci_cloud_guard_cloud_guard_configuration.existing.reporting_region == var.region
      error_message = "region must equal the existing Cloud Guard reporting region."
    }
  }
}

resource "oci_ons_subscription" "email" {
  for_each = var.email_recipients

  compartment_id = var.notification_compartment_id
  topic_id       = oci_ons_notification_topic.cloudguard.topic_id
  protocol       = "EMAIL"
  endpoint       = each.value
}

resource "oci_events_rule" "cloudguard" {
  compartment_id = coalesce(var.events_compartment_id, var.tenancy_id)
  display_name   = "${var.name_prefix}_problems"
  description    = "Route selected Cloud Guard problem events to email"
  is_enabled     = var.is_enabled
  # jsonencode keeps this compatible with OCI provider 7.x and Freewheel-limits.
  condition = jsonencode(local.event_condition)

  actions {
    action {
      action_type = "ONS"
      is_enabled  = var.is_enabled
      topic_id    = oci_ons_notification_topic.cloudguard.topic_id
      description = "Notify the configured email subscribers"
    }
  }
}
