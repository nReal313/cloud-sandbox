variable "project_id" {
  description = "Google Cloud project that contains the datasets/buckets."
  type        = string
}

variable "google_service_account_email" {
  description = "Google service account email that receives data access."
  type        = string
}

variable "bigquery_dataset_roles" {
  description = "Map of short dataset IDs to IAM roles granted on each dataset. Datasets must already exist."
  type        = map(string)
  default     = {}
}

variable "gcs_bucket_roles" {
  description = "Map of bucket names to IAM roles granted on each bucket. Buckets must already exist."
  type        = map(string)
  default     = {}
}
