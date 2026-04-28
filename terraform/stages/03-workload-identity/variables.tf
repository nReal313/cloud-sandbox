variable "project_id" {
  description = "Google Cloud project that hosts the GSA and GKE Workload Identity pool."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Namespace that contains the Kubernetes service account."
  type        = string
  default     = "sandbox"
}

variable "kubernetes_service_account_name" {
  description = "Name of the Kubernetes service account that impersonates the Google service account."
  type        = string
  default     = "cloud-sandbox"
}

variable "google_service_account_id" {
  description = "Short ID for the Google service account to create."
  type        = string
  default     = "cloud-sandbox-runtime"
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

variable "return_principal_id_as_email" {
  description = "Whether to add the GKE annotation that exposes the principal ID as an email-like identifier."
  type        = bool
  default     = true
}
