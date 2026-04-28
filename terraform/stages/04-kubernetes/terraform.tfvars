project_id = "metricsamp"
region     = "us-central1"

gke_cluster_name = "cloud-sandbox-cluster"
container_image  = "alyosha313/cloud_sandbox:v1.0.2"

kubernetes_namespace            = "sandbox"
kubernetes_service_account_name = "cloud-sandbox"
google_service_account_email    = "cloud-sandbox-runtime@metricsamp.iam.gserviceaccount.com"
