data "google_project" "this" {
  project_id = var.project_id
}

resource "google_service_account" "this" {
  account_id   = var.google_service_account_id
  display_name = coalesce(var.google_service_account_display_name, var.google_service_account_id)
  description  = var.google_service_account_description
  project      = var.project_id
}

locals {
  workload_identity_member = "principal://iam.googleapis.com/projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${var.project_id}.svc.id.goog/subject/ns/${var.kubernetes_namespace}/sa/${var.kubernetes_service_account_name}"
  kubernetes_service_account_annotations = merge(
    {
      "iam.gke.io/gcp-service-account" = google_service_account.this.email
    },
    var.return_principal_id_as_email ? {
      "iam.gke.io/return-principal-id-as-email" = "true"
    } : {}
  )
}

resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.this.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.workload_identity_member
}

resource "google_project_iam_member" "project_roles" {
  for_each = toset(var.project_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.this.email}"
}

resource "google_bigquery_dataset_iam_member" "dataset_roles" {
  for_each = var.bigquery_dataset_roles

  dataset_id = each.key
  role       = each.value
  member     = "serviceAccount:${google_service_account.this.email}"
}

resource "google_storage_bucket_iam_member" "bucket_roles" {
  for_each = var.gcs_bucket_roles

  bucket = each.key
  role   = each.value
  member = "serviceAccount:${google_service_account.this.email}"
}
