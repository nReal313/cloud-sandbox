# Terraform

This directory provisions the Google Cloud service account and Workload Identity binding that the sandbox pod uses in GKE.

## What it creates

- one Google service account for the sandbox workload
- project-level IAM roles for BigQuery job execution and Firestore access
- optional dataset-level BigQuery access
- optional bucket-level GCS access
- Workload Identity binding from the Kubernetes service account to the Google service account

## How to use

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

The default values assume:

- the GKE cluster and the Google service account live in the same project
- the Kubernetes service account is named `cloud-sandbox`
- the namespace is `sandbox`

## Outputs

The module prints:

- the Google service account email
- the Workload Identity member string
- the Kubernetes service account annotations you should apply
- a `kubectl annotate` command you can run directly

## Kubernetes service account annotation

The pod deployment in `k8s/base/deployment.yaml` uses the `cloud-sandbox` Kubernetes service account.
Apply the Terraform output to that service account so GKE can mint tokens for the Google service account:

```yaml
metadata:
  annotations:
    iam.gke.io/gcp-service-account: cloud-sandbox-runtime@my-gcp-project.iam.gserviceaccount.com
    iam.gke.io/return-principal-id-as-email: "true"
```

The exact email value comes from Terraform output.
