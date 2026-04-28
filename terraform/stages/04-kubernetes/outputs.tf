output "container_image" {
  value = var.container_image
}

output "gateway_address_command" {
  value = "kubectl get gateway cloud-sandbox-gateway -n ${var.kubernetes_namespace} -o jsonpath='{.status.addresses[0].value}'"
}

output "sandbox_base_url_command" {
  value = "echo http://$(kubectl get gateway cloud-sandbox-gateway -n ${var.kubernetes_namespace} -o jsonpath='{.status.addresses[0].value}')"
}

output "load_balancer_address_command" {
  value = "kubectl get service cloud-sandbox-public -n ${var.kubernetes_namespace} -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
}

output "load_balancer_base_url_command" {
  value = "echo http://$(kubectl get service cloud-sandbox-public -n ${var.kubernetes_namespace} -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
}
