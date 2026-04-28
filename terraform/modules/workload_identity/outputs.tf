output "google_service_account_email" {
  value = google_service_account.this.email
}

output "google_service_account_name" {
  value = google_service_account.this.name
}

output "google_service_account_resource_id" {
  value = google_service_account.this.id
}

output "workload_identity_member" {
  value = local.workload_identity_member
}

output "kubernetes_service_account_annotations" {
  value = local.kubernetes_service_account_annotations
}

output "gcloud_annotate_command" {
  value = format(
    "kubectl annotate serviceaccount %s -n %s iam.gke.io/gcp-service-account=%s --overwrite",
    var.kubernetes_service_account_name,
    var.kubernetes_namespace,
    google_service_account.this.email,
  )
}
