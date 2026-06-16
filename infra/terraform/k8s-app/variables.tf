variable "kube_config_path" {
  description = "Path to the kubeconfig file Terraform should use."
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace for ChatLite."
  type        = string
  default     = "chatlite"
}

variable "app_name" {
  description = "Application name used for Kubernetes resource names."
  type        = string
  default     = "chatlite"
}

variable "image" {
  description = "Container image to deploy. Use a registry image for remote clusters."
  type        = string
  default     = "anitalluri00/chatlite:latest"
}

variable "image_pull_policy" {
  description = "Image pull policy for the ChatLite container."
  type        = string
  default     = "Always"
}

variable "replicas" {
  description = "Replica count. Keep this at 1 when using SQLite storage."
  type        = number
  default     = 1
}

variable "app_secret" {
  description = "Stable app secret used to encrypt/decrypt stored chat messages."
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Optional PostgreSQL URL. Leave null to use SQLite on the persistent volume."
  type        = string
  sensitive   = true
  default     = null
}

variable "sqlite_storage_size" {
  description = "Persistent volume claim size for SQLite data."
  type        = string
  default     = "1Gi"
}

variable "storage_class_name" {
  description = "Optional Kubernetes storage class name. Leave null to use the cluster default."
  type        = string
  default     = null
}

variable "ingress_enabled" {
  description = "Whether to create an Ingress resource."
  type        = bool
  default     = false
}

variable "ingress_host" {
  description = "Host name for the optional Ingress."
  type        = string
  default     = "chatlite.example.com"
}

variable "ingress_class_name" {
  description = "Ingress class name, for example nginx."
  type        = string
  default     = "nginx"
}
