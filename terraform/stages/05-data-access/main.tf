provider "google" {
  project = var.project_id
}

resource "google_bigquery_dataset_iam_member" "dataset_roles" {
  for_each = var.bigquery_dataset_roles

  dataset_id = each.key
  role       = each.value
  member     = "serviceAccount:${var.google_service_account_email}"
}

resource "google_storage_bucket_iam_member" "bucket_roles" {
  for_each = var.gcs_bucket_roles

  bucket = each.key
  role   = each.value
  member = "serviceAccount:${var.google_service_account_email}"
}
