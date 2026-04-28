locals {
  return_principal_id_as_email = tostring(var.return_principal_id_as_email)
}

resource "terraform_data" "kubernetes_apply" {
  triggers_replace = {
    project_id                      = var.project_id
    cluster_name                    = var.gke_cluster_name
    cluster_location                = var.region
    namespace                       = var.kubernetes_namespace
    kubernetes_service_account_name = var.kubernetes_service_account_name
    google_service_account_email    = var.google_service_account_email
    return_principal_id_as_email    = local.return_principal_id_as_email
    container_image                 = var.container_image
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail

      gcloud container clusters get-credentials ${var.gke_cluster_name} \
        --region ${var.region} \
        --project ${var.project_id}

      kubectl apply -f - <<'YAML'
      apiVersion: v1
      kind: Namespace
      metadata:
        name: ${var.kubernetes_namespace}
      ---
      apiVersion: v1
      kind: ServiceAccount
      metadata:
        name: ${var.kubernetes_service_account_name}
        namespace: ${var.kubernetes_namespace}
        labels:
          app.kubernetes.io/name: cloud-sandbox
        annotations:
          iam.gke.io/gcp-service-account: ${var.google_service_account_email}
          iam.gke.io/return-principal-id-as-email: "${local.return_principal_id_as_email}"
      ---
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: cloud-sandbox
        namespace: ${var.kubernetes_namespace}
      spec:
        replicas: 1
        selector:
          matchLabels:
            app.kubernetes.io/name: cloud-sandbox
        template:
          metadata:
            labels:
              app.kubernetes.io/name: cloud-sandbox
          spec:
            runtimeClassName: gvisor
            serviceAccountName: ${var.kubernetes_service_account_name}
            securityContext:
              runAsUser: 1000
              runAsGroup: 1000
              fsGroup: 1000
            containers:
              - name: api
                image: ${var.container_image}
                imagePullPolicy: Always
                ports:
                  - containerPort: 8080
                    name: http
                env:
                  - name: PORT
                    value: "8080"
                securityContext:
                  allowPrivilegeEscalation: false
                  readOnlyRootFilesystem: true
                  runAsNonRoot: true
                  capabilities:
                    drop:
                      - ALL
                volumeMounts:
                  - name: tmp
                    mountPath: /tmp
            volumes:
              - name: tmp
                emptyDir: {}
      ---
      apiVersion: v1
      kind: Service
      metadata:
        name: cloud-sandbox
        namespace: ${var.kubernetes_namespace}
      spec:
        selector:
          app.kubernetes.io/name: cloud-sandbox
        ports:
          - name: http
            port: 80
            targetPort: http
        type: ClusterIP
      ---
      apiVersion: v1
      kind: Service
      metadata:
        name: cloud-sandbox-public
        namespace: ${var.kubernetes_namespace}
      spec:
        selector:
          app.kubernetes.io/name: cloud-sandbox
        ports:
          - name: http
            port: 80
            targetPort: http
        type: LoadBalancer
      ---
      apiVersion: gateway.networking.k8s.io/v1
      kind: Gateway
      metadata:
        name: cloud-sandbox-gateway
        namespace: ${var.kubernetes_namespace}
      spec:
        gatewayClassName: gke-l7-global-external-managed
        listeners:
          - name: http
            protocol: HTTP
            port: 80
            allowedRoutes:
              kinds:
                - kind: HTTPRoute
      ---
      apiVersion: gateway.networking.k8s.io/v1
      kind: HTTPRoute
      metadata:
        name: cloud-sandbox
        namespace: ${var.kubernetes_namespace}
      spec:
        parentRefs:
          - name: cloud-sandbox-gateway
        rules:
          - matches:
              - path:
                  type: PathPrefix
                  value: /
            backendRefs:
              - name: cloud-sandbox
                port: 80
      YAML
    EOT
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail

      gcloud container clusters get-credentials ${self.triggers_replace.cluster_name} \
        --region ${self.triggers_replace.cluster_location} \
        --project ${self.triggers_replace.project_id}

      kubectl delete httproute cloud-sandbox -n ${self.triggers_replace.namespace} --ignore-not-found
      kubectl delete gateway cloud-sandbox-gateway -n ${self.triggers_replace.namespace} --ignore-not-found
      kubectl delete service cloud-sandbox-public -n ${self.triggers_replace.namespace} --ignore-not-found
      kubectl delete service cloud-sandbox -n ${self.triggers_replace.namespace} --ignore-not-found
      kubectl delete deployment cloud-sandbox -n ${self.triggers_replace.namespace} --ignore-not-found
      kubectl delete serviceaccount ${self.triggers_replace.kubernetes_service_account_name} -n ${self.triggers_replace.namespace} --ignore-not-found
      kubectl delete namespace ${self.triggers_replace.namespace} --ignore-not-found
    EOT
  }
}
