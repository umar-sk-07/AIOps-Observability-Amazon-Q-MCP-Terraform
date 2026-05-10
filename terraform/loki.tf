# =============================================================================
# LOKI LOGGING STACK INSTALLATION - WORKING CONFIGURATION
# =============================================================================

resource "helm_release" "loki" {
  count = var.enable_monitoring ? 1 : 0

  name             = "loki"
  namespace        = "monitoring"
  create_namespace = false

  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki"
  version    = "6.16.0"

  timeout = 600

  values = [
    yamlencode({
      # Deploy in SingleBinary mode
      deploymentMode = "SingleBinary"
      
      # Single binary configuration
      singleBinary = {
        replicas = 1
        
        # Add emptyDir volume for writable storage
        extraVolumes = [
          {
            name = "loki-data"
            emptyDir = {}
          }
        ]
        
        extraVolumeMounts = [
          {
            name = "loki-data"
            mountPath = "/var/loki"
          }
        ]
        
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
        
        persistence = {
          enabled = false
        }
      }
      
      # Disable other modes
      backend = {
        replicas = 0
      }
      read = {
        replicas = 0
      }
      write = {
        replicas = 0
      }
      
      # Loki configuration
      loki = {
        auth_enabled = false
        
        commonConfig = {
          replication_factor = 1
          path_prefix = "/var/loki"
        }
        
        storage = {
          type = "filesystem"
        }
        
        schemaConfig = {
          configs = [
            {
              from = "2024-01-01"
              store = "tsdb"
              object_store = "filesystem"
              schema = "v13"
              index = {
                prefix = "index_"
                period = "24h"
              }
            }
          ]
        }
        
        limits_config = {
          retention_period = "168h"
          ingestion_rate_mb = 4
          ingestion_burst_size_mb = 6
          per_stream_rate_limit = "3MB"
          per_stream_rate_limit_burst = "15MB"
        }
        
        server = {
          http_listen_port = 3100
          grpc_listen_port = 9095
        }
        
        # Disable ruler to avoid read-only filesystem issues
        ruler = {
          enable_api = false
          storage = {
            type = "local"
            local = {
              directory = "/var/loki/rules"
            }
          }
        }
      }
      
      # Gateway configuration
      gateway = {
        enabled = true
        replicas = 1
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
      }
      
      # Disable monitoring features
      monitoring = {
        selfMonitoring = {
          enabled = false
          grafanaAgent = {
            installOperator = false
          }
        }
        lokiCanary = {
          enabled = false
        }
      }
      
      test = {
        enabled = false
      }
      
      chunksCache = {
        enabled = false
      }
      
      resultsCache = {
        enabled = false
      }
    })
  ]

  depends_on = [
    module.eks_addons,
    time_sleep.wait_for_cluster
  ]
}

# Promtail for log collection
resource "helm_release" "promtail" {
  count = var.enable_monitoring ? 1 : 0

  name             = "promtail"
  namespace        = "monitoring"
  create_namespace = false

  repository = "https://grafana.github.io/helm-charts"
  chart      = "promtail"
  version    = "6.16.5"

  values = [
    yamlencode({
      config = {
        clients = [
          {
            url = "http://loki-gateway/loki/api/v1/push"
          }
        ]
      }
      
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
    })
  ]

  depends_on = [
    helm_release.loki
  ]
}

# Grafana datasource
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
            url       = "http://loki-gateway:80"
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
    helm_release.promtail,
    module.eks_addons
  ]
}
