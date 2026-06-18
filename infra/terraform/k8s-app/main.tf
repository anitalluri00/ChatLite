provider "kubernetes" {
  config_path = pathexpand(var.kube_config_path)
}

locals {
  labels = {
    "app.kubernetes.io/name"      = var.app_name
    "app.kubernetes.io/component" = "web"
    "app.kubernetes.io/part-of"   = "chatlite"
  }
}

resource "kubernetes_namespace_v1" "chatlite" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name"    = var.app_name
      "app.kubernetes.io/part-of" = "chatlite"
    }
  }
}

resource "kubernetes_secret_v1" "chatlite" {
  metadata {
    name      = "${var.app_name}-secret"
    namespace = kubernetes_namespace_v1.chatlite.metadata[0].name
    labels    = local.labels
  }

  type = "Opaque"

  data = merge(
    {
      CHATLITE_APP_SECRET = var.app_secret
    },
    var.database_url == null ? {} : {
      CHATLITE_DATABASE_URL = var.database_url
    }
  )
}

resource "kubernetes_config_map_v1" "chatlite" {
  metadata {
    name      = "${var.app_name}-config"
    namespace = kubernetes_namespace_v1.chatlite.metadata[0].name
    labels    = local.labels
  }

  data = {
    PORT                      = "8501"
    STREAMLIT_SERVER_ADDRESS  = "0.0.0.0"
    STREAMLIT_SERVER_HEADLESS = "true"
    CHATLITE_REALTIME_WS_URL  = var.realtime_ws_url
    CHATLITE_SQLITE_FILE      = "/app/data/chatlite_data.sqlite3"
  }
}

resource "kubernetes_persistent_volume_claim_v1" "chatlite" {
  metadata {
    name      = "${var.app_name}-data"
    namespace = kubernetes_namespace_v1.chatlite.metadata[0].name
    labels    = local.labels
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class_name

    resources {
      requests = {
        storage = var.sqlite_storage_size
      }
    }
  }
}

resource "kubernetes_deployment_v1" "chatlite" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace_v1.chatlite.metadata[0].name
    labels    = local.labels
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = local.labels
    }

    template {
      metadata {
        labels = local.labels
      }

      spec {
        container {
          name              = var.app_name
          image             = var.image
          image_pull_policy = var.image_pull_policy

          port {
            name           = "http"
            container_port = 8501
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.chatlite.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret_v1.chatlite.metadata[0].name
            }
          }

          volume_mount {
            name       = "chatlite-data"
            mount_path = "/app/data"
          }

          readiness_probe {
            http_get {
              path = "/_stcore/health"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/_stcore/health"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 30
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }

        volume {
          name = "chatlite-data"

          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.chatlite.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "chatlite" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace_v1.chatlite.metadata[0].name
    labels    = local.labels
  }

  spec {
    type = "ClusterIP"

    selector = local.labels

    port {
      name        = "http"
      port        = 80
      target_port = "http"
    }
  }
}

resource "kubernetes_ingress_v1" "chatlite" {
  count = var.ingress_enabled ? 1 : 0

  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace_v1.chatlite.metadata[0].name
    labels    = local.labels
  }

  spec {
    ingress_class_name = var.ingress_class_name

    rule {
      host = var.ingress_host

      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service_v1.chatlite.metadata[0].name

              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
