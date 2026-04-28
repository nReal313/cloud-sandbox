#!/usr/bin/env bash
set -euo pipefail

# Edit these defaults here, or override them with environment variables:
#   PROJECT_ID=my-project REGION=us-east1 ./deploy.sh
PROJECT_ID="${PROJECT_ID:-metricsamp}"
REGION="${REGION:-us-central1}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-alyosha313/cloud_sandbox:v1.0.2}"
AUTO_APPROVE="${AUTO_APPROVE:-false}"

GKE_CLUSTER_NAME="${GKE_CLUSTER_NAME:-cloud-sandbox-cluster}"
KUBERNETES_NAMESPACE="${KUBERNETES_NAMESPACE:-sandbox}"
KUBERNETES_SERVICE_ACCOUNT_NAME="${KUBERNETES_SERVICE_ACCOUNT_NAME:-cloud-sandbox}"
GOOGLE_SERVICE_ACCOUNT_ID="${GOOGLE_SERVICE_ACCOUNT_ID:-cloud-sandbox-runtime}"

SYSTEM_NODE_POOL_NAME="${SYSTEM_NODE_POOL_NAME:-system-pool}"
SYSTEM_MACHINE_TYPE="${SYSTEM_MACHINE_TYPE:-e2-medium}"
SYSTEM_DISK_SIZE_GB="${SYSTEM_DISK_SIZE_GB:-20}"
SYSTEM_DISK_TYPE="${SYSTEM_DISK_TYPE:-pd-standard}"

SANDBOX_NODE_POOL_NAME="${SANDBOX_NODE_POOL_NAME:-sandbox-pool}"
SANDBOX_MACHINE_TYPE="${SANDBOX_MACHINE_TYPE:-e2-medium}"
SANDBOX_DISK_SIZE_GB="${SANDBOX_DISK_SIZE_GB:-20}"
SANDBOX_DISK_TYPE="${SANDBOX_DISK_TYPE:-pd-standard}"
SANDBOX_NODE_MIN_COUNT="${SANDBOX_NODE_MIN_COUNT:-1}"
SANDBOX_NODE_MAX_COUNT="${SANDBOX_NODE_MAX_COUNT:-3}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

tf_apply() {
  local stage="$1"
  shift
  local apply_args=()
  if [[ "${AUTO_APPROVE}" == "true" ]]; then
    apply_args+=("-auto-approve")
  fi

  echo
  echo "==> Applying ${stage}"
  terraform -chdir="${ROOT_DIR}/stages/${stage}" init
  terraform -chdir="${ROOT_DIR}/stages/${stage}" workspace select "${PROJECT_ID}" >/dev/null 2>&1 \
    || terraform -chdir="${ROOT_DIR}/stages/${stage}" workspace new "${PROJECT_ID}" >/dev/null
  terraform -chdir="${ROOT_DIR}/stages/${stage}" apply "${apply_args[@]}" "$@"
}

tf_output_raw() {
  local stage="$1"
  local name="$2"
  terraform -chdir="${ROOT_DIR}/stages/${stage}" workspace select "${PROJECT_ID}" >/dev/null
  terraform -chdir="${ROOT_DIR}/stages/${stage}" output -raw "$name"
}

require_command terraform
require_command gcloud
require_command kubectl

echo "Deploying cloud sandbox"
echo "  project:          ${PROJECT_ID}"
echo "  region:           ${REGION}"
echo "  cluster:          ${GKE_CLUSTER_NAME}"
echo "  namespace:        ${KUBERNETES_NAMESPACE}"
echo "  container image:  ${CONTAINER_IMAGE}"
echo "  auto approve:     ${AUTO_APPROVE}"

tf_apply "01-project" \
  -var="project_id=${PROJECT_ID}"

tf_apply "02-cluster" \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="gke_cluster_name=${GKE_CLUSTER_NAME}" \
  -var="system_node_pool_name=${SYSTEM_NODE_POOL_NAME}" \
  -var="system_machine_type=${SYSTEM_MACHINE_TYPE}" \
  -var="system_disk_size_gb=${SYSTEM_DISK_SIZE_GB}" \
  -var="system_disk_type=${SYSTEM_DISK_TYPE}" \
  -var="sandbox_node_pool_name=${SANDBOX_NODE_POOL_NAME}" \
  -var="sandbox_machine_type=${SANDBOX_MACHINE_TYPE}" \
  -var="sandbox_disk_size_gb=${SANDBOX_DISK_SIZE_GB}" \
  -var="sandbox_disk_type=${SANDBOX_DISK_TYPE}" \
  -var="sandbox_node_min_count=${SANDBOX_NODE_MIN_COUNT}" \
  -var="sandbox_node_max_count=${SANDBOX_NODE_MAX_COUNT}"

tf_apply "03-workload-identity" \
  -var="project_id=${PROJECT_ID}" \
  -var="kubernetes_namespace=${KUBERNETES_NAMESPACE}" \
  -var="kubernetes_service_account_name=${KUBERNETES_SERVICE_ACCOUNT_NAME}" \
  -var="google_service_account_id=${GOOGLE_SERVICE_ACCOUNT_ID}"

GOOGLE_SERVICE_ACCOUNT_EMAIL="$(tf_output_raw "03-workload-identity" "google_service_account_email")"

tf_apply "04-kubernetes" \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="gke_cluster_name=${GKE_CLUSTER_NAME}" \
  -var="container_image=${CONTAINER_IMAGE}" \
  -var="kubernetes_namespace=${KUBERNETES_NAMESPACE}" \
  -var="kubernetes_service_account_name=${KUBERNETES_SERVICE_ACCOUNT_NAME}" \
  -var="google_service_account_email=${GOOGLE_SERVICE_ACCOUNT_EMAIL}"

echo
echo "==> Waiting for cloud-sandbox deployment rollout"
kubectl rollout status deployment/cloud-sandbox \
  -n "${KUBERNETES_NAMESPACE}" \
  --timeout=300s

echo
echo "==> Waiting for Gateway address"
for _ in {1..40}; do
  GATEWAY_ADDRESS="$(kubectl get gateway cloud-sandbox-gateway \
    -n "${KUBERNETES_NAMESPACE}" \
    -o jsonpath='{.status.addresses[0].value}' 2>/dev/null || true)"
  if [[ -n "${GATEWAY_ADDRESS}" ]]; then
    break
  fi
  sleep 15
done

if [[ -z "${GATEWAY_ADDRESS:-}" ]]; then
  echo "Gateway is still provisioning. Check later with:" >&2
  echo "  kubectl get gateway cloud-sandbox-gateway -n ${KUBERNETES_NAMESPACE}" >&2
fi

echo
echo "==> Waiting for direct LoadBalancer address"
for _ in {1..40}; do
  LOAD_BALANCER_ADDRESS="$(kubectl get service cloud-sandbox-public \
    -n "${KUBERNETES_NAMESPACE}" \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)"
  if [[ -n "${LOAD_BALANCER_ADDRESS}" ]]; then
    break
  fi
  sleep 15
done

SANDBOX_URL=""
if [[ -n "${GATEWAY_ADDRESS:-}" ]]; then
  SANDBOX_URL="http://${GATEWAY_ADDRESS}"
  echo "Gateway URL: ${SANDBOX_URL}"
fi

if [[ -n "${LOAD_BALANCER_ADDRESS:-}" ]]; then
  SANDBOX_URL="http://${LOAD_BALANCER_ADDRESS}"
  echo "Direct LoadBalancer URL: ${SANDBOX_URL}"
fi

if [[ -z "${SANDBOX_URL}" ]]; then
  echo "No external address is ready yet." >&2
  exit 0
fi

echo
echo "Testing sandbox URL: ${SANDBOX_URL}"
echo "Health check:"
curl -fsS "${SANDBOX_URL}/health" || true
echo
