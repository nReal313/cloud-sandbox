variable "project_id" {
  description = "Google Cloud project that hosts the GKE cluster."
  type        = string
}

variable "region" {
  description = "Google Cloud region for the GKE cluster."
  type        = string
  default     = "us-central1"
}

variable "gke_cluster_name" {
  description = "Name of the existing GKE cluster."
  type        = string
  default     = "cloud-sandbox-cluster"
}

variable "container_image" {
  description = "Fully-qualified external container image deployed to GKE."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Namespace that contains the sandbox workload."
  type        = string
  default     = "sandbox"
}

variable "kubernetes_service_account_name" {
  description = "Name of the Kubernetes service account used by the sandbox workload."
  type        = string
  default     = "cloud-sandbox"
}

variable "google_service_account_email" {
  description = "Google service account email used for Workload Identity annotation."
  type        = string
}

variable "return_principal_id_as_email" {
  description = "Whether to add the GKE annotation that exposes the principal ID as an email-like identifier."
  type        = bool
  default     = true
}
