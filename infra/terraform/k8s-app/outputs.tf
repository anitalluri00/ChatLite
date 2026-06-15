output "namespace" {
  description = "Namespace where ChatLite is deployed."
  value       = kubernetes_namespace_v1.chatlite.metadata[0].name
}

output "service_name" {
  description = "ClusterIP service name."
  value       = kubernetes_service_v1.chatlite.metadata[0].name
}

output "service_port" {
  description = "Service port for ChatLite."
  value       = 80
}

output "ingress_host" {
  description = "Ingress host when ingress is enabled."
  value       = var.ingress_enabled ? var.ingress_host : null
}
