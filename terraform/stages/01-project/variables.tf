variable "project_id" {
  description = "Google Cloud project to prepare."
  type        = string
}

variable "enabled_project_services" {
  description = "Google Cloud APIs required by the sandbox stack."
  type        = list(string)
  default = [
    "bigquery.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "container.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ]
}
