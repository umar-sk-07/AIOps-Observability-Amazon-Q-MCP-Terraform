# AIOps: Intelligent Incident Response & Remediation on AWS

<div align="center">

![Banner](./docs/images/banner.png)

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.33-326CE5?logo=kubernetes&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform&logoColor=white)
![ArgoCD](https://img.shields.io/badge/ArgoCD-GitOps-EF7B4D?logo=argo&logoColor=white)
![AWS EKS](https://img.shields.io/badge/AWS-EKS%20Auto%20Mode-FF9900?logo=amazonaws&logoColor=white)
![Amazon Q](https://img.shields.io/badge/Amazon%20Q-Agentic%20AI-232F3E?logo=amazonaws&logoColor=white)

**A production-grade AIOps platform where Amazon Q autonomously investigates Kubernetes incidents, performs root cause analysis, and executes human-approved remediations — all in real time.**

</div>

---

## What This Project Does

When a Kubernetes alert fires, most teams get paged and manually dig through logs, events, and metrics to figure out what broke. This project eliminates that manual loop.

**The full automated flow:**

1. AlertManager detects an issue in the EKS cluster and fires a webhook
2. A FastAPI server on EC2 receives the alert and triggers Amazon Q CLI
3. Amazon Q (agentic AI) investigates the cluster autonomously using MCP tools
4. Amazon Q posts a full Root Cause Analysis + 3 remediation options to Discord
5. A human replies with `1`, `2`, or `3` to approve an action
6. Amazon Q executes the approved remediation via EKS MCP
7. Amazon Q posts final confirmation to Discord

**No one touches `kubectl` manually. No one digs through logs. The AI does the investigation — humans make the call.**

---

## System Architecture

![AIOps Architecture](./docs/images/ChatGPT%20Image%20May%2010%2C%202026%2C%2003_35_33%20PM.png)

### How the Three Layers Connect

**Layer 1 — Amazon EKS Cluster**
- 5 retail store microservices running as containers
- ArgoCD managing GitOps deployments
- Full observability stack: Prometheus (metrics), Loki (logs), Grafana (dashboards), AlertManager (alerts)

**Layer 2 — EC2 AI Engine**
- **FastAPI**: Receives AlertManager webhooks, maintains incident conversation history, manages the remediation workflow
- **Amazon Q CLI**: The agentic reasoning layer — investigates, reasons, decides, and acts
- **MCP Tool Layer**:
  - **EKS MCP** (`awslabs.eks-mcp-server`) — kubectl access, cluster state, pod logs, events, scaling
  - **Discord MCP** (`barryy625/mcp-discord`) — posts RCA to Discord, polls for human replies

**Layer 3 — Discord Incident Channel**
- Amazon Q posts: Incident Summary → Root Cause Analysis → 3 remediation options
- Human replies: `"1"`, `"2"`, or `"3"` to approve
- Amazon Q executes the approved action and posts final confirmation

---

## Application Architecture

The retail store is a 5-service microservices application — deliberately decoupled with different languages, databases, and Helm charts to simulate real enterprise complexity.

![Application Architecture](./docs/images/application-architecture.png)

![Containers](./docs/images/containers.png)

| Service | Language | Database | Description |
|---------|----------|----------|-------------|
| **UI** | Java 21 / Spring Boot 3.5 | — | Store frontend |
| **Catalog** | Go 1.23 / Gin | MySQL | Product catalog REST API |
| **Cart** | Java 21 / Spring Boot 3.5 | Amazon DynamoDB | Shopping cart API |
| **Orders** | Java 21 / Spring Boot 3.5 | PostgreSQL + RabbitMQ | Order processing API |
| **Checkout** | Node.js 20 | — | Checkout orchestration API |

All services expose Prometheus metrics, health check endpoints, chaos engineering endpoints, and OpenTelemetry instrumentation.

### Application UI

| Default Theme | Orange Theme |
|:---:|:---:|
| ![Default Theme](./docs/images/theme-default.png) | ![Orange Theme](./docs/images/theme-orange.png) |

![Screenshot](./docs/images/screenshot.png)

---

## Infrastructure

Everything is provisioned with a single `terraform apply`.

```
terraform/
├── main.tf        # VPC + EKS cluster (Auto Mode)
├── addons.tf      # NGINX Ingress, Cert Manager, Prometheus, Loki
├── argocd.tf      # ArgoCD Helm installation
├── loki.tf        # Loki logging stack
├── security.tf    # Security groups
├── variables.tf   # Input variables
└── outputs.tf     # Cluster endpoint, load balancer URL
```

**What gets provisioned:**
- VPC with public/private subnets across 3 AZs + NAT Gateway
- EKS Cluster (Kubernetes 1.33) with **Auto Mode** — no node group management
- NGINX Ingress Controller with Network Load Balancer
- Cert Manager for SSL
- ArgoCD for GitOps
- Kube Prometheus Stack (Prometheus + Grafana + AlertManager)
- Loki + Promtail for log aggregation

![EKS Deployment](docs/images/EKS.gif)

---

## GitOps with ArgoCD

ArgoCD continuously reconciles the cluster against this Git repository. Any drift is automatically corrected.

![ArgoCD UI](./docs/images/argocd-ui.png)

```
Git Push → ArgoCD detects change → Helm renders manifests → Applied to EKS
                                          ↑
                               prune: true + selfHeal: true
```

**Dual-branch strategy:**

| Branch | Images | CI/CD | Use Case |
|--------|--------|-------|----------|
| `main` | Public ECR (v1.2.2) | Manual | Demos, quick testing |
| `production` | Private ECR (commit hash) | GitHub Actions | Full GitOps workflow |

On the `production` branch, any push to `src/` triggers GitHub Actions → builds Docker image → pushes to ECR → ArgoCD auto-syncs to EKS.

---

## Monitoring & Observability

```
monitoring/
├── prometheus-rules.yaml    # 8 alert rules
├── alertmanager-config.yaml # Routes retail-store alerts to AIOps webhook
├── podmonitor.yaml          # Prometheus scrape config for all services
└── kustomization.yaml
```

### Alert Rules

| Alert | Severity | Condition |
|-------|----------|-----------|
| `PodCrashLooping` | Critical | >3 restarts in 15 min |
| `ServiceDown` | Critical | 0 replicas available for 1 min |
| `HighErrorRate` | Critical | >5% HTTP 5xx for 2 min |
| `PodNotReady` | Warning | Not Running for 5 min |
| `HighCPUUsage` | Warning | >80% CPU limit for 5 min |
| `HighMemoryUsage` | Warning | >80% memory limit for 5 min |
| `HighLatency` | Warning | p95 latency >1s for 5 min |
| `DeploymentReplicasMismatch` | Warning | Desired ≠ Available for 5 min |

AlertManager routes only `retail-store` namespace alerts to the AIOps webhook receiver on EC2. Critical alerts fire immediately; warnings are grouped.

---

## AIOps Incident Response — Deep Dive

### The Agentic Investigation Loop

When Amazon Q receives an alert, it doesn't follow a fixed script. It reasons about the alert type and runs targeted checks:

**Always checked:**
- Current pod status in `retail-store` namespace
- Recent events for the affected pod/deployment
- Pod logs (current + previous container if restarted)
- Deployment replica status

**Checked based on alert type:**
- Node resource pressure → for CPU/memory alerts
- HPA status → for replica mismatch alerts
- Rollout history → for crash or error rate alerts
- Dependency service health → for latency alerts (e.g. if checkout is slow, also checks orders and cart)
- ArgoCD sync status → for any deployment-related alert

### What Discord Sees

**Immediate notification:**
```
🔴 ALERT: PodCrashLooping
Investigating... analyzing cluster with MCP tools.
Namespace: retail-store | Target: catalog-7d9f8b-xxx | Severity: critical
```

**RCA posted after investigation:**
```
🔍 RCA Complete: PodCrashLooping

📋 Root Cause:
OOMKilled — container memory limit (256Mi) exceeded under load.
Exit code 137 confirmed. Previous container logs show heap exhaustion.

📊 Evidence:
- kube_pod_container_status_restarts_total: 5 in last 10 min
- Last exit reason: OOMKilled
- Memory usage: 98% of limit at time of crash

🔧 Remediation Options:

1️⃣  Quick Fix (~2 min):
Delete and restart the affected pod

2️⃣  Standard Fix (~10 min):
Scale deployment to 0 then back up, verify all pods healthy

3️⃣  Deep Fix (~30 min):
Patch memory limits on deployment, verify stability, re-enable ArgoCD auto-sync

❌  Type 'no' to take no action
⏰  Waiting for your response (timeout: 5 minutes)
```

**After human replies `"2"`:**
```
✅ Remediation Complete: PodCrashLooping

Action Taken: Scaled deployment to 0, then back to 2 replicas
Result: All pods Running and Ready
Verification: 2/2 replicas available, no restarts in last 2 min
```

### Approval Boundaries

| Operation | Approval Required |
|-----------|------------------|
| `kubectl get`, `describe`, `logs`, `top`, `events` | Never — read-only, always permitted |
| Posting to Discord | Never |
| `kubectl delete`, `scale`, `patch`, `rollout restart` | Always — human must reply first |
| ArgoCD sync or rollback | Always |
| No human response within 5 min | Auto-exit, no action taken |

---

## Getting Started

### Prerequisites

| Tool | Version |
|------|---------|
| AWS CLI | v2+ |
| Terraform | 1.0+ |
| kubectl | 1.33+ |
| Helm | 3.0+ |

### 1. Configure AWS

```bash
aws configure
```

### 2. Clone and deploy infrastructure

```bash
git clone <your-repo-url>
cd retail-store-sample-app/terraform
terraform init
terraform apply --auto-approve
```

### 3. Configure kubectl

```bash
aws eks update-kubeconfig --name retail-store --region ap-south-1
kubectl get nodes
```

### 4. Access the application

```bash
# Get load balancer external IP
kubectl get svc -n ingress-nginx

# Verify all services are running
kubectl get pods -n retail-store
```

### 5. Access ArgoCD

```bash
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d

# Port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080 — username: admin
```

### 6. Deploy monitoring configuration

```bash
# Update alertmanager-config.yaml with your EC2 webhook IP first, then:
kubectl apply -f monitoring/prometheus-rules.yaml
kubectl apply -f monitoring/podmonitor.yaml
kubectl apply -f monitoring/alertmanager-config.yaml

kubectl rollout restart statefulset \
  alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

### 7. Access observability UIs

```bash
# Grafana (admin / prom-operator)
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80

# Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090

# AlertManager
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
```

---

## Cleanup

```bash
cd terraform
terraform destroy --auto-approve
```

> ECR repositories must be deleted manually from the AWS Console.

---

## Tech Stack

| Category | Technologies |
|----------|-------------|
| **Cloud** | AWS (EKS, EC2, VPC, DynamoDB, ECR, IAM) |
| **IaC** | Terraform, AWS EKS Blueprints Addons |
| **Orchestration** | Kubernetes 1.33, EKS Auto Mode |
| **GitOps** | ArgoCD, Helm |
| **CI/CD** | GitHub Actions |
| **Ingress** | NGINX Ingress Controller, NLB |
| **Monitoring** | Prometheus, Grafana, AlertManager |
| **Logging** | Loki, Promtail |
| **Tracing** | OpenTelemetry 2.17 |
| **AIOps Engine** | Amazon Q CLI (agentic), FastAPI, MCP |
| **MCP Tools** | EKS MCP, Discord MCP |
| **Languages** | Java 21, Go 1.23, Node.js 20 |
| **Frameworks** | Spring Boot 3.5, Gin, Express |
| **Databases** | MySQL, PostgreSQL, Amazon DynamoDB, RabbitMQ |

---

## License

Apache License 2.0 — see [LICENSE](./LICENSE) for details.
