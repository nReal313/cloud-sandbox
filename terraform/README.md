# Terraform

This Terraform setup is intentionally staged. GKE, Workload Identity, Kubernetes
resources, and optional data IAM grants have different dependencies, so each
stage is applied separately.

## Stages

1. `stages/01-project`
   Enables required Google Cloud APIs.

2. `stages/02-cluster`
   Creates the regional GKE Standard cluster, a regular system node pool, and a
   gVisor-enabled sandbox node pool.

3. `stages/03-workload-identity`
   Creates the Google service account, grants project-level runtime roles, and
   binds the Kubernetes service account identity to the Google service account.

4. `stages/04-kubernetes`
   Uses local `gcloud` and `kubectl` to apply the namespace, Kubernetes service
   account, Deployment, internal Service, direct LoadBalancer Service, Gateway,
   and HTTPRoute.

5. `stages/05-data-access`
   Optional. Grants dataset-level BigQuery and bucket-level GCS access to the
   sandbox Google service account. Only use this after the datasets/buckets
   exist and your Terraform identity can manage their IAM.

## Apply Order

The easiest path is the deploy script:

```bash
cd terraform
./deploy.sh
```

Edit the variables at the top of `deploy.sh`, or override them with environment
variables:

```bash
PROJECT_ID=metricsamp REGION=us-east1 ./deploy.sh
```

To skip the Terraform approval prompt for each stage:

```bash
AUTO_APPROVE=true ./deploy.sh
```

The script applies stages 1-4 in order and passes the Google service account
email from stage 3 into stage 4 automatically.

Manual staged apply is still available. Run these from the repo root:

```bash
cd terraform/stages/01-project
terraform init
terraform apply

cd ../02-cluster
terraform init
terraform apply

cd ../03-workload-identity
terraform init
terraform apply

cd ../04-kubernetes
terraform init
terraform apply
```

The Kubernetes stage requires local `gcloud` and `kubectl` to be installed and
authenticated. It runs `gcloud container clusters get-credentials` before
applying manifests.

The data-access stage is optional:

```bash
cd ../05-data-access
terraform init
terraform apply
```

By default, `05-data-access/terraform.tfvars` leaves both maps empty:

```hcl
bigquery_dataset_roles = {}
gcs_bucket_roles       = {}
```

Add entries only for resources that already exist, for example:

```hcl
bigquery_dataset_roles = {
  analytics = "roles/bigquery.dataViewer"
}

gcs_bucket_roles = {
  sandbox-bucket = "roles/storage.objectAdmin"
}
```

## Current Defaults

The staged `terraform.tfvars` files currently target:

```hcl
project_id      = "metricsamp"
region          = "us-central1"
container_image = "alyosha313/cloud_sandbox:v1.0.2"
```

The node pools are intentionally small to avoid quota issues:

```hcl
system_machine_type  = "e2-medium"
system_disk_size_gb  = 20
system_disk_type     = "pd-standard"
sandbox_machine_type = "e2-medium"
sandbox_disk_size_gb = 20
sandbox_disk_type    = "pd-standard"
```

## Gateway URL

After stage 4 completes, get the Gateway IP:

```bash
kubectl get gateway cloud-sandbox-gateway \
  -n sandbox \
  -o jsonpath='{.status.addresses[0].value}'
```

Build the base URL:

```bash
SANDBOX_URL="http://$(kubectl get gateway cloud-sandbox-gateway -n sandbox -o jsonpath='{.status.addresses[0].value}')"
curl "$SANDBOX_URL/health"
```

There is also a direct LoadBalancer Service fallback:

```bash
SANDBOX_URL="http://$(kubectl get service cloud-sandbox-public -n sandbox -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
curl "$SANDBOX_URL/health"
```

Expected response:

```json
{"status":"ok"}
```

## Cleanup

Destroy in reverse order:

```bash
cd terraform/stages/05-data-access
terraform destroy

cd ../04-kubernetes
terraform destroy

cd ../03-workload-identity
terraform destroy

cd ../02-cluster
terraform destroy

cd ../01-project
terraform destroy
```

For `01-project`, API resources use `disable_on_destroy = false`, so destroying
the stage removes Terraform state ownership but does not disable APIs.
