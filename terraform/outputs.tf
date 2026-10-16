output "topic_id" {
  description = "Dedicated Cloud Guard Notifications topic OCID."
  value       = oci_ons_notification_topic.cloudguard.topic_id
}

output "events_rule_id" {
  value = oci_events_rule.cloudguard.id
}

output "events_compartment_id" {
  value = oci_events_rule.cloudguard.compartment_id
}

output "event_condition" {
  description = "Actual nested filter sent to OCI Events."
  value       = local.event_condition
}

output "subscription_ids" {
  description = "Each recipient must confirm their subscription; creation alone does not activate email delivery."
  value       = { for email, subscription in oci_ons_subscription.email : email => subscription.id }
}
