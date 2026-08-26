# Executable GCP L1 edge for six-layer-eventing@1.
#
# The public edge exposes only MQTT over TLS. BifroMQ delegates the generated
# deployment credential and the two allowed topic directions to the bounded
# adapter webhook. The adapter forwards telemetry to the authenticated Cloud
# Run ingress and delivers command events back to MQTT with acknowledgement on
# the destination side. This is intentionally a small thesis-PoC device edge,
# not a general device registry or certificate authority.

locals {
  gcp_six_layer_bifromq_image = "docker.io/apache/bifromq@sha256:14856495892e3b84d25092a90de3c2fc149a3482afd283abb95fdff18effd924"
  gcp_six_layer_adapter_replicas = (
    local.gcp_six_layer_bifromq_integration_nodes > 0
    ? local.gcp_six_layer_bifromq_integration_nodes
    : 1
  )
  gcp_six_layer_bifromq_auth_url = (
    "http://bifromq-auth.${local.gcp_six_layer_bifromq_namespace}.svc.cluster.local:8080"
  )
}

resource "random_password" "gcp_six_layer_mqtt_device_username" {
  count   = local.gcp_six_layer_l1_enabled ? 1 : 0
  length  = 20
  special = false
  upper   = false
}

resource "random_password" "gcp_six_layer_mqtt_device_password" {
  count   = local.gcp_six_layer_l1_enabled ? 1 : 0
  length  = 32
  special = false
}

resource "random_password" "gcp_six_layer_mqtt_bridge_username" {
  count   = local.gcp_six_layer_l1_enabled ? 1 : 0
  length  = 20
  special = false
  upper   = false
}

resource "random_password" "gcp_six_layer_mqtt_bridge_password" {
  count   = local.gcp_six_layer_l1_enabled ? 1 : 0
  length  = 32
  special = false
}

resource "google_compute_address" "gcp_six_layer_mqtt" {
  count        = local.gcp_six_layer_l1_enabled ? 1 : 0
  project      = local.gcp_project_id
  region       = var.gcp_region
  name         = "${local.gcp_six_layer_name}-six-mqtt"
  description  = "Static address for the authenticated Six-layer MQTT PoC edge"
  address_type = "EXTERNAL"
  network_tier = "PREMIUM"
  labels       = local.gcp_six_layer_labels

  depends_on = [terraform_data.gcp_six_layer_foundation_guard]
}

resource "tls_private_key" "gcp_six_layer_mqtt" {
  count       = local.gcp_six_layer_l1_enabled ? 1 : 0
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_self_signed_cert" "gcp_six_layer_mqtt" {
  count           = local.gcp_six_layer_l1_enabled ? 1 : 0
  private_key_pem = tls_private_key.gcp_six_layer_mqtt[0].private_key_pem

  subject {
    common_name  = google_compute_address.gcp_six_layer_mqtt[0].address
    organization = "Twin2MultiCloud thesis PoC"
  }

  ip_addresses          = [google_compute_address.gcp_six_layer_mqtt[0].address]
  validity_period_hours = 8760
  early_renewal_hours   = 168
  allowed_uses = [
    "digital_signature",
    "key_encipherment",
    "server_auth",
  ]
}

resource "kubernetes_config_map_v1" "gcp_six_layer_bifromq" {
  count = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0

  metadata {
    name      = "bifromq-config"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels    = local.gcp_six_layer_labels
  }

  data = {
    "standalone.yml" = <<-YAML
      authProviderFQN: "org.apache.bifromq.demo.plugin.DemoAuthProvider"
      mqttServiceConfig:
        server:
          maxMsgByteSize: 262144
          tcpListener:
            enable: true
            host: "0.0.0.0"
            port: 1883
          tlsListener:
            enable: true
            host: "0.0.0.0"
            port: 1884
            sslConfig:
              certFile: "/home/bifromq/tls/tls.crt"
              keyFile: "/home/bifromq/tls/tls.key"
              clientAuth: "NONE"
          wsListener:
            enable: false
          wssListener:
            enable: false
      clusterConfig:
        env: "${local.gcp_six_layer_name}-v2"
        port: 8899
        clusterDomainName: "bifromq-headless.${local.gcp_six_layer_bifromq_namespace}.svc.cluster.local"
      YAML
  }

  depends_on = [
    kubernetes_namespace_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard,
  ]
}

resource "kubernetes_secret_v1" "gcp_six_layer_bifromq" {
  count = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0

  metadata {
    name      = "bifromq-runtime"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels    = local.gcp_six_layer_labels
  }

  data = {
    "tls.crt"         = tls_self_signed_cert.gcp_six_layer_mqtt[0].cert_pem
    "tls.key"         = tls_private_key.gcp_six_layer_mqtt[0].private_key_pem
    "device-username" = random_password.gcp_six_layer_mqtt_device_username[0].result
    "device-password" = random_password.gcp_six_layer_mqtt_device_password[0].result
    "bridge-username" = random_password.gcp_six_layer_mqtt_bridge_username[0].result
    "bridge-password" = random_password.gcp_six_layer_mqtt_bridge_password[0].result
  }
  type = "Opaque"

  depends_on = [
    kubernetes_namespace_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard,
  ]
}

resource "kubernetes_service_v1" "gcp_six_layer_bifromq_headless" {
  count = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0

  metadata {
    name      = "bifromq-headless"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels    = local.gcp_six_layer_labels
  }

  spec {
    cluster_ip                  = "None"
    publish_not_ready_addresses = true
    selector = {
      app = "bifromq"
    }

    port {
      name        = "cluster"
      port        = 8899
      target_port = "cluster"
      protocol    = "TCP"
    }

    port {
      name        = "mqtt"
      port        = 1883
      target_port = "mqtt"
      protocol    = "TCP"
    }
  }
}

resource "kubernetes_deployment_v1" "gcp_apache_bifromq_4_0_0_incubating_on_gke_standard" {
  count            = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0
  wait_for_rollout = true

  metadata {
    name      = "bifromq"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels = merge(local.gcp_six_layer_labels, {
      component = "bifromq"
    })
  }

  spec {
    replicas = local.gcp_six_layer_bifromq_broker_nodes

    selector {
      match_labels = {
        app = "bifromq"
      }
    }

    template {
      metadata {
        labels = merge(local.gcp_six_layer_labels, {
          app       = "bifromq"
          component = "bifromq"
        })
      }

      spec {
        security_context {
          run_as_non_root = true
        }

        affinity {
          pod_anti_affinity {
            required_during_scheduling_ignored_during_execution {
              label_selector {
                match_labels = {
                  app = "bifromq"
                }
              }
              topology_key = "kubernetes.io/hostname"
            }
          }
        }

        node_selector = {
          workload = "bifromq-broker"
        }

        container {
          name  = "bifromq"
          image = local.gcp_six_layer_bifromq_image

          image_pull_policy = "IfNotPresent"

          env {
            name  = "MEM_LIMIT"
            value = "25769803776"
          }
          env {
            name  = "EXTRA_JVM_OPTS"
            value = "-Dplugin.authprovider.url=${local.gcp_six_layer_bifromq_auth_url}"
          }

          port {
            name           = "mqtt"
            container_port = 1883
            protocol       = "TCP"
          }
          port {
            name           = "mqtt-tls"
            container_port = 1884
            protocol       = "TCP"
          }
          port {
            name           = "cluster"
            container_port = 8899
            protocol       = "TCP"
          }

          resources {
            requests = {
              cpu    = "6"
              memory = "24Gi"
            }
            limits = {
              cpu    = "7"
              memory = "25Gi"
            }
          }

          readiness_probe {
            tcp_socket {
              port = "mqtt"
            }
            initial_delay_seconds = 20
            period_seconds        = 10
            timeout_seconds       = 2
            failure_threshold     = 12
          }

          liveness_probe {
            tcp_socket {
              port = "mqtt"
            }
            initial_delay_seconds = 60
            period_seconds        = 20
            timeout_seconds       = 2
            failure_threshold     = 6
          }

          volume_mount {
            name       = "config"
            mount_path = "/home/bifromq/conf/standalone.yml"
            sub_path   = "standalone.yml"
            read_only  = true
          }
          volume_mount {
            name       = "tls"
            mount_path = "/home/bifromq/tls"
            read_only  = true
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map_v1.gcp_six_layer_bifromq[0].metadata[0].name
          }
        }
        volume {
          name = "tls"
          secret {
            secret_name = kubernetes_secret_v1.gcp_six_layer_bifromq[0].metadata[0].name
            items {
              key  = "tls.crt"
              path = "tls.crt"
            }
            items {
              key  = "tls.key"
              path = "tls.key"
              # Secret volumes are already pod-local and read-only. The
              # upstream image runs as a non-root UID, so a root-owned 0400
              # file would make the private key unreadable at startup.
              mode = "0444"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_container_node_pool.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard,
    kubernetes_config_map_v1.gcp_six_layer_bifromq,
    kubernetes_secret_v1.gcp_six_layer_bifromq,
    kubernetes_service_v1.gcp_six_layer_bifromq_headless,
  ]
}

resource "kubernetes_service_v1" "gcp_gcp_external_load_balancer" {
  count = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0

  metadata {
    name      = "bifromq-mqtt"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels    = local.gcp_six_layer_labels
  }

  spec {
    type             = "LoadBalancer"
    load_balancer_ip = google_compute_address.gcp_six_layer_mqtt[0].address
    selector = {
      app = "bifromq"
    }

    port {
      name        = "mqtt-tls"
      port        = 8883
      target_port = "mqtt-tls"
      protocol    = "TCP"
    }
  }

  depends_on = [
    kubernetes_deployment_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard,
  ]
}

resource "kubernetes_service_account_v1" "gcp_six_layer_mqtt_adapter" {
  count = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0

  metadata {
    name      = "mqtt-adapter"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels    = local.gcp_six_layer_labels
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.gcp_six_layer_runtime["ingress"].email
    }
  }
}

resource "google_service_account_iam_member" "gcp_six_layer_mqtt_adapter_workload_identity" {
  count              = local.gcp_six_layer_l1_enabled ? 1 : 0
  service_account_id = google_service_account.gcp_six_layer_runtime["ingress"].name
  role               = "roles/iam.workloadIdentityUser"
  member = format(
    "serviceAccount:%s.svc.id.goog[%s/mqtt-adapter]",
    local.gcp_project_id,
    local.gcp_six_layer_bifromq_namespace,
  )
}

resource "google_cloud_run_v2_service_iam_member" "gcp_six_layer_ingress_invoker" {
  count    = local.gcp_six_layer_l1_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["ingress"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_six_layer_runtime["ingress"].email}"
}

resource "google_pubsub_subscription" "gcp_six_layer_command_adapter" {
  count                        = local.gcp_six_layer_l1_enabled ? 1 : 0
  project                      = local.gcp_project_id
  name                         = "${local.gcp_six_layer_name}-six-command-adapter"
  topic                        = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["command"].id
  ack_deadline_seconds         = 60
  message_retention_duration   = "1209600s"
  enable_message_ordering      = true
  retain_acked_messages        = false
  enable_exactly_once_delivery = false
  labels                       = local.gcp_six_layer_labels

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic = local.gcp_six_layer_event_layer_local ? (
      google_pubsub_topic.domain_events["failure"].id
    ) : google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["failure"].id
    max_delivery_attempts = local.gcp_six_layer_event_layer_local ? (
      var.gcp_event_max_delivery_attempts
    ) : 5
  }
}

resource "google_pubsub_subscription_iam_member" "gcp_six_layer_command_adapter" {
  count        = local.gcp_six_layer_l1_enabled ? 1 : 0
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.gcp_six_layer_command_adapter[0].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.gcp_six_layer_runtime["ingress"].email}"
}

resource "google_pubsub_subscription_iam_member" "gcp_six_layer_command_failure_service_agent" {
  count        = local.gcp_six_layer_l1_enabled ? 1 : 0
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.gcp_six_layer_command_adapter[0].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.gcp_six_layer_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "kubernetes_service_v1" "gcp_six_layer_bifromq_auth" {
  count = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0

  metadata {
    name      = "bifromq-auth"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels    = local.gcp_six_layer_labels
  }

  spec {
    selector = {
      app = "mqtt-adapter"
    }
    port {
      name        = "http"
      port        = 8080
      target_port = "http"
      protocol    = "TCP"
    }
  }
}

resource "kubernetes_deployment_v1" "gcp_gcp_ordered_mqtt_pubsub_adapter" {
  count            = local.gcp_six_layer_l1_enabled && var.gcp_six_layer_kubernetes_stage_enabled ? 1 : 0
  wait_for_rollout = true

  metadata {
    name      = "mqtt-adapter"
    namespace = local.gcp_six_layer_bifromq_namespace
    labels = merge(local.gcp_six_layer_labels, {
      component = "mqtt-adapter"
    })
  }

  spec {
    replicas = local.gcp_six_layer_adapter_replicas

    selector {
      match_labels = {
        app = "mqtt-adapter"
      }
    }

    template {
      metadata {
        labels = merge(local.gcp_six_layer_labels, {
          app       = "mqtt-adapter"
          component = "mqtt-adapter"
        })
      }

      spec {
        service_account_name = kubernetes_service_account_v1.gcp_six_layer_mqtt_adapter[0].metadata[0].name

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
        }

        affinity {
          pod_anti_affinity {
            required_during_scheduling_ignored_during_execution {
              label_selector {
                match_labels = {
                  app = "mqtt-adapter"
                }
              }
              topology_key = "kubernetes.io/hostname"
            }
          }
        }

        node_selector = {
          workload = local.gcp_six_layer_bifromq_integration_nodes > 0 ? "bifromq-integration" : "bifromq-broker"
        }

        container {
          name    = "mqtt-adapter"
          image   = var.gcp_six_layer_platform_image
          command = ["python", "mqtt_adapter.py"]

          image_pull_policy = "IfNotPresent"

          port {
            name           = "http"
            container_port = 8080
            protocol       = "TCP"
          }

          env {
            name  = "PORT"
            value = "8080"
          }
          env {
            name  = "BIFROMQ_HOST"
            value = "bifromq-headless.${local.gcp_six_layer_bifromq_namespace}.svc.cluster.local"
          }
          env {
            name  = "BIFROMQ_PORT"
            value = "1883"
          }
          env {
            name  = "BIFROMQ_TENANT_ID"
            value = local.gcp_six_layer_name
          }
          env {
            name  = "INGRESS_URL"
            value = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["ingress"].uri
          }
          env {
            name  = "COMMAND_SUBSCRIPTION"
            value = google_pubsub_subscription.gcp_six_layer_command_adapter[0].id
          }
          env {
            name = "BIFROMQ_DEVICE_USERNAME"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.gcp_six_layer_bifromq[0].metadata[0].name
                key  = "device-username"
              }
            }
          }
          env {
            name = "BIFROMQ_DEVICE_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.gcp_six_layer_bifromq[0].metadata[0].name
                key  = "device-password"
              }
            }
          }
          env {
            name = "BIFROMQ_BRIDGE_USERNAME"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.gcp_six_layer_bifromq[0].metadata[0].name
                key  = "bridge-username"
              }
            }
          }
          env {
            name = "BIFROMQ_BRIDGE_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.gcp_six_layer_bifromq[0].metadata[0].name
                key  = "bridge-password"
              }
            }
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "1"
              memory = "512Mi"
            }
          }

          readiness_probe {
            http_get {
              path = "/healthz"
              port = "http"
            }
            initial_delay_seconds = 10
            period_seconds        = 10
            timeout_seconds       = 2
            failure_threshold     = 12
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = "http"
            }
            initial_delay_seconds = 30
            period_seconds        = 20
            timeout_seconds       = 2
            failure_threshold     = 6
          }
        }
      }
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.gcp_six_layer_ingress_invoker,
    google_container_node_pool.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard,
    google_container_node_pool.gcp_gcp_ordered_mqtt_pubsub_adapter,
    google_pubsub_subscription_iam_member.gcp_six_layer_command_adapter,
    google_service_account_iam_member.gcp_six_layer_mqtt_adapter_workload_identity,
    kubernetes_deployment_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard,
    kubernetes_service_v1.gcp_six_layer_bifromq_auth,
  ]
}
