output "gke_cluster_name" {
  value = google_container_cluster.sandbox.name
}

output "gke_cluster_location" {
  value = google_container_cluster.sandbox.location
}

output "workload_pool" {
  value = google_container_cluster.sandbox.workload_identity_config[0].workload_pool
}

output "get_credentials_command" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.sandbox.name} --region ${google_container_cluster.sandbox.location} --project ${var.project_id}"
}
