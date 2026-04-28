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
  description = "Name of the GKE cluster to create."
  type        = string
  default     = "cloud-sandbox-cluster"
}

variable "gke_release_channel" {
  description = "GKE release channel."
  type        = string
  default     = "REGULAR"
}

variable "gke_deletion_protection" {
  description = "Whether to enable deletion protection on the GKE cluster."
  type        = bool
  default     = false
}

variable "system_node_pool_name" {
  description = "Name of the regular non-sandbox node pool required by GKE Sandbox on Standard clusters."
  type        = string
  default     = "system-pool"
}

variable "system_node_count" {
  description = "Initial number of nodes in the regular system node pool."
  type        = number
  default     = 1
}

variable "system_machine_type" {
  description = "Machine type for regular system node pool nodes."
  type        = string
  default     = "e2-medium"
}

variable "system_disk_size_gb" {
  description = "Boot disk size in GB for regular system node pool nodes."
  type        = number
  default     = 20
}

variable "system_disk_type" {
  description = "Boot disk type for regular system node pool nodes."
  type        = string
  default     = "pd-standard"
}

variable "sandbox_node_pool_name" {
  description = "Name of the gVisor-enabled sandbox node pool."
  type        = string
  default     = "sandbox-pool"
}

variable "sandbox_node_count" {
  description = "Initial number of nodes in the sandbox node pool."
  type        = number
  default     = 1
}

variable "sandbox_node_min_count" {
  description = "Minimum node count for the sandbox node pool autoscaler."
  type        = number
  default     = 1
}

variable "sandbox_node_max_count" {
  description = "Maximum node count for the sandbox node pool autoscaler."
  type        = number
  default     = 3
}

variable "sandbox_machine_type" {
  description = "Machine type for sandbox node pool nodes."
  type        = string
  default     = "e2-medium"
}

variable "sandbox_disk_size_gb" {
  description = "Boot disk size in GB for sandbox node pool nodes."
  type        = number
  default     = 20
}

variable "sandbox_disk_type" {
  description = "Boot disk type for sandbox node pool nodes."
  type        = string
  default     = "pd-standard"
}
