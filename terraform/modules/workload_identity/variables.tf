variable "project_id" {
  description = "Google Cloud project that hosts the GSA and the GKE Workload Identity pool."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Namespace that contains the Kubernetes service account."
  type        = string
}

variable "kubernetes_service_account_name" {
  description = "Name of the Kubernetes service account that will impersonate the Google service account."
  type        = string
}

variable "google_service_account_id" {
  description = "Short ID for the Google service account to create."
  type        = string
}

variable "google_service_account_display_name" {
  description = "Optional display name for the Google service account."
  type        = string
  default     = null
}

variable "google_service_account_description" {
  description = "Optional description for the Google service account."
  type        = string
  default     = null
}

variable "project_roles" {
  description = "Project-level IAM roles granted to the Google service account."
  type        = list(string)
  default = [
    "roles/bigquery.jobUser",
    "roles/datastore.user",
  ]
}

variable "bigquery_dataset_roles" {
  description = "Map of short dataset IDs to IAM roles granted on each dataset."
  type        = map(string)
  default     = {}
}

variable "gcs_bucket_roles" {
  description = "Map of bucket names to IAM roles granted on each bucket."
  type        = map(string)
  default     = {}
}

variable "return_principal_id_as_email" {
  description = "Whether to add the GKE annotation that exposes the principal ID as an email-like identifier."
  type        = bool
  default     = true
}
