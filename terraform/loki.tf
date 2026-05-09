# =============================================================================
# LOKI LOGGING STACK INSTALLATION
# =============================================================================

# =============================================================================
# LOKI HELM INSTALLATION
# =============================================================================

resource "helm_release" "loki" {
  count = var.enable_monitoring ? 1 : 0

  name             = "loki"
  namespace        = "monitoring"
  create_namespace = false  # monitoring namespace created by kube-prometheus-stack

  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  version    = "2.10.2"  # Stable version

  # Loki configuration values
  values = [
    yamlencode({
      # Loki server configuration
      loki = {
        enabled = true
        
        # Disable authentication for internal cluster use
        auth_enabled = false
        
        # Single binary mode for simplicity
        deploymentMode = "SingleBinary"
        
        # Storage configuration - filesystem (ephemeral)
        storage = {
          type = "filesystem"
        }
        
        # Retention configuration
        limits_config = {
          retention_period = "168h"  # 7 days
        }
        
        # Resource limits
        resources = {
          requests = {
            cpu    = "100m"
            memory = "128Mi"
          }
          limits = {
            cpu    = "200m"
            memory = "256Mi"
          }
        }
      }
      
      # Promtail configuration (log collection agent)
      promtail = {
        enabled = true
        
        # Resource limits for Promtail DaemonSet
        resources = {
          requests = {
            cpu    = "50m"
            memory = "64Mi"
          }
          limits = {
            cpu    = "100m"
            memory = "128Mi"
          }
        }
        
        # Configure Promtail to extract Kubernetes labels
        config = {
          snippets = {
            pipelineStages = [
              {
                docker = {}
              },
              {
                cri = {}
              }
            ]
          }
        }
      }
      
      # Disable Grafana (already installed by kube-prometheus-stack)
      grafana = {
        enabled = false
      }
      
      # Disable Prometheus (already installed)
      prometheus = {
        enabled = false
      }
    })
  ]

  depends_on = [
    module.eks_addons,
    time_sleep.wait_for_cluster
  ]
}

# =============================================================================
# CONFIGURE LOKI AS GRAFANA DATASOURCE
# =============================================================================

resource "kubectl_manifest" "grafana_loki_datasource" {
  count = var.enable_monitoring ? 1 : 0

  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {
      name      = "grafana-loki-datasource"
      namespace = "monitoring"
      labels = {
        grafana_datasource = "1"
      }
    }
    data = {
      "loki-datasource.yaml" = yamlencode({
        apiVersion = 1
        datasources = [
          {
            name      = "Loki"
            type      = "loki"
            access    = "proxy"
            url       = "http://loki:3100"
            isDefault = false
            jsonData = {
              maxLines = 1000
            }
          }
        ]
      })
    }
  })

  depends_on = [
    helm_release.loki,
    module.eks_addons
  ]
}
