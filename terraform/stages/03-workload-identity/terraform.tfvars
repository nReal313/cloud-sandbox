project_id = "metricsamp"

kubernetes_namespace            = "sandbox"
kubernetes_service_account_name = "cloud-sandbox"
google_service_account_id       = "cloud-sandbox-runtime"

project_roles = [
  "roles/bigquery.jobUser",
  "roles/datastore.user",
]
