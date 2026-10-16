variable "region" {
  description = "Existing Cloud Guard reporting region, which can differ from the tenancy home region."
  type        = string
}

variable "oci_profile" {
  description = "OCI configuration profile used by Terraform and the deployment scripts."
  type        = string
  default     = "DEFAULT"
}

variable "tenancy_id" {
  description = "Tenancy OCID supplied by deploy_stack.py from the selected OCI profile."
  type        = string
  validation {
    condition     = can(regex("^ocid1\\.tenancy\\.[^<> ]+$", var.tenancy_id))
    error_message = "tenancy_id must be a tenancy OCID from the selected OCI profile."
  }
}

variable "notification_compartment_id" {
  description = "Existing compartment for the new Notifications topic and email subscriptions."
  type        = string
  validation {
    condition     = can(regex("^ocid1\\.(compartment|tenancy)\\.[^<> ]+$", var.notification_compartment_id))
    error_message = "notification_compartment_id must be a compartment or tenancy OCID."
  }
}

variable "events_compartment_id" {
  description = "Rule scope: null uses tenancy root; otherwise choose a parent containing the emitted problem events."
  type        = string
  default     = null
  validation {
    condition     = var.events_compartment_id == null ? true : can(regex("^ocid1\\.(compartment|tenancy)\\.[^<> ]+$", var.events_compartment_id))
    error_message = "events_compartment_id must be null or a compartment/tenancy OCID."
  }
}

variable "name_prefix" {
  description = "Prefix for the rule and dedicated Notifications topic."
  type        = string
  default     = "cloudguard_alerts"
  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_-]{0,79}$", var.name_prefix))
    error_message = "name_prefix must start with a letter and contain up to 80 letters, digits, underscores or hyphens."
  }
}

variable "email_recipients" {
  description = "Recipients must confirm the email subscription after deployment."
  type        = set(string)
  validation {
    condition     = length(var.email_recipients) > 0 && alltrue([for email in var.email_recipients : can(regex("^[^ <>@]+@[^ <>@]+\\.[^ <>@]+$", email))])
    error_message = "Provide at least one email address without spaces or placeholders."
  }
}

variable "problem_event_types" {
  description = "Problem lifecycle notifications. Default: newly detected problems only."
  type        = set(string)
  default     = ["com.oraclecloud.cloudguard.problemdetected"]
  validation {
    condition = length(var.problem_event_types) > 0 && alltrue([for value in var.problem_event_types : contains([
      "com.oraclecloud.cloudguard.problemdetected",
      "com.oraclecloud.cloudguard.problemdismissed",
      "com.oraclecloud.cloudguard.problemremediated"
    ], value)])
    error_message = "Select supported Cloud Guard problem detected, dismissed or remediated event types."
  }
}

variable "risk_levels" {
  description = "Exact additionalDetails.riskLevel values; empty matches all severities. Verify against a real event before restricting."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for value in var.risk_levels : contains(["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINOR"], value)])
    error_message = "risk_levels supports CRITICAL, HIGH, MEDIUM, LOW and MINOR."
  }
}

variable "target_ids" {
  description = "Exact Cloud Guard target OCIDs to match; empty matches all targets within the Events rule scope. Does not create or modify targets."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for value in var.target_ids : can(regex("^ocid1\\.cloudguardtarget\\.[^<> ]+$", value))])
    error_message = "target_ids must contain existing Cloud Guard target OCIDs."
  }
}

variable "is_enabled" {
  description = "Enable or pause the Events rule and its notification action."
  type        = bool
  default     = true
}
