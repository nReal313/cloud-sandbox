provider "google" {
  project = var.project_id
}

module "sandbox_workload_identity" {
  source = "../../modules/workload_identity"

  project_id                          = var.project_id
  kubernetes_namespace                = var.kubernetes_namespace
  kubernetes_service_account_name     = var.kubernetes_service_account_name
  google_service_account_id           = var.google_service_account_id
  google_service_account_display_name = var.google_service_account_display_name
  google_service_account_description  = var.google_service_account_description
  project_roles                       = var.project_roles
  bigquery_dataset_roles              = {}
  gcs_bucket_roles                    = {}
  return_principal_id_as_email        = var.return_principal_id_as_email
}
