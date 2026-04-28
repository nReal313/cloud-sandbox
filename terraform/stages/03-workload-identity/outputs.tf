output "google_service_account_email" {
  value = module.sandbox_workload_identity.google_service_account_email
}

output "google_service_account_name" {
  value = module.sandbox_workload_identity.google_service_account_name
}

output "workload_identity_member" {
  value = module.sandbox_workload_identity.workload_identity_member
}

output "kubernetes_service_account_annotations" {
  value = module.sandbox_workload_identity.kubernetes_service_account_annotations
}
