# =============================================================================
# EKS ADD-ONS AND EXTENSIONS
# =============================================================================

module "eks_addons" {
  source  = "aws-ia/eks-blueprints-addons/aws"
  version = "~> 1.0"

  # Cluster information
  cluster_name      = module.retail_app_eks.cluster_name
  cluster_endpoint  = module.retail_app_eks.cluster_endpoint
  cluster_version   = module.retail_app_eks.cluster_version
  oidc_provider_arn = module.retail_app_eks.oidc_provider_arn

  # =============================================================================
  # NGINX INGRESS CONTROLLER - Load Balancing and Routing
  # =============================================================================
  enable_ingress_nginx = true
  ingress_nginx = {
    most_recent = true
    namespace   = "ingress-nginx"
    
    # Basic configuration
    set = [
      {
        name  = "controller.service.type"
        value = "LoadBalancer"
      },
      {
        name  = "controller.service.externalTrafficPolicy"
        value = "Local"
      },
      {
        name  = "controller.resources.requests.cpu"
        value = "100m"
      },
      {
        name  = "controller.resources.requests.memory"
        value = "128Mi"
      },
      {
        name  = "controller.resources.limits.cpu"
        value = "200m"
      },
      {
        name  = "controller.resources.limits.memory"
        value = "256Mi"
      }
    ]
    
    # AWS Load Balancer specific annotations
    set_sensitive = [
      {
        name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-scheme"
        value = "internet-facing"
      },
      {
        name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-type"
        value = "nlb"
      },
      {
        name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-nlb-target-type"
        value = "instance"
      },
      {
        name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-health-check-path"
        value = "/healthz"
      },
      {
        name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-health-check-port"
        value = "10254"
      },
      {
        name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-health-check-protocol"
        value = "HTTP"
      }
    ]
  }

  # =============================================================================
  # MONITORING STACK - Prometheus, AlertManager, Grafana
  # =============================================================================
  
  enable_kube_prometheus_stack = var.enable_monitoring
  kube_prometheus_stack = {
    most_recent = true
    namespace   = "monitoring"
    
    # Prometheus configuration
    set = [
      # Enable persistent storage for Prometheus
      {
        name  = "prometheus.prometheusSpec.retention"
        value = "7d"
      },
      {
        name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.accessModes[0]"
        value = "ReadWriteOnce"
      },
      {
        name  = "prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage"
        value = "10Gi"
      },
      # Enable service monitors for application metrics
      {
        name  = "prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues"
        value = "false"
      },
      {
        name  = "prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues"
        value = "false"
      },
      # AlertManager configuration
      {
        name  = "alertmanager.enabled"
        value = "true"
      },
      {
        name  = "alertmanager.alertmanagerSpec.retention"
        value = "120h"
      },
      # Grafana configuration
      {
        name  = "grafana.enabled"
        value = "true"
      },
      {
        name  = "grafana.adminPassword"
        value = "prom-operator"
      }
    ]
  }

  # =============================================================================
  # OPTIONAL: AWS LOAD BALANCER CONTROLLER
  # =============================================================================
  # enable_aws_load_balancer_controller = true
  # aws_load_balancer_controller = {
  #   most_recent = true
  #   namespace   = "kube-system"
  # }

  depends_on = [module.retail_app_eks]
}
