# Retail Store Monitoring & Alerting Guide

Complete guide to set up Prometheus monitoring, AlertManager, and test the alerting system with ArgoCD.

---

## Prerequisites

- EKS cluster running
- kubectl configured
- ArgoCD installed and managing retail-store-app
- EC2 instance for receiving alerts (webhook endpoint)

---

## Step 1: Enable Monitoring Stack (5 minutes)

Deploy the Prometheus monitoring stack using Terraform:

```bash
cd terraform

# Enable monitoring in your terraform.tfvars
echo 'enable_monitoring = true' >> terraform.tfvars

# Apply the configuration
terraform apply

# Wait for all monitoring pods to be running
kubectl get pods -n monitoring -w
```

**Expected pods:**
- `prometheus-kube-prometheus-stack-prometheus-0`
- `alertmanager-kube-prometheus-stack-alertmanager-0`
- `kube-prometheus-stack-grafana-xxx`
- `kube-prometheus-stack-operator-xxx`
- `kube-state-metrics-xxx`
- `prometheus-node-exporter-xxx`

---

## Step 2: Configure AlertManager with Your EC2 IP (2 minutes)

Update the AlertManager configuration with your EC2 instance IP:

```bash
# Edit the alertmanager config file
nano monitoring/alertmanager-config.yaml

# Find this line and replace with your EC2 IP:
# url: 'http://<YOUR_EC2_IP>:5000/alert'
```

**Example:**
```yaml
receivers:
  - name: 'aiops-receiver'
    webhook_configs:
      - url: 'http://13.126.124.216:5000/alert'
```

---

## Step 3: Deploy Monitoring Configuration (3 minutes)

Apply all monitoring configurations:

```bash
# Apply Prometheus alert rules
kubectl apply -f monitoring/prometheus-rules.yaml

# Apply PodMonitor (tells Prometheus to scrape retail-store pods)
kubectl apply -f monitoring/podmonitor.yaml

# Apply AlertManager configuration
kubectl apply -f monitoring/alertmanager-config.yaml

# Restart AlertManager to pick up new config
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring

# Wait for restart to complete
kubectl rollout status statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

---

## Step 4: Verify Everything is Working (3 minutes)

### 4.1 Check Prometheus Targets

```bash
# Port-forward to Prometheus (run in separate terminal or background)
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```

Open: **http://localhost:9090/targets**

**Expected:** You should see `podMonitor/monitoring/retail-store/0` with **5/5 UP**:
- ✅ carts
- ✅ catalog
- ✅ checkout
- ✅ orders
- ✅ ui

### 4.2 Check Prometheus Rules

Open: **http://localhost:9090/rules**

**Expected:** You should see `retail-store-alerts` group with these rules:
- PodCrashLooping
- PodNotReady
- HighCPUUsage
- HighMemoryUsage
- HighErrorRate
- ServiceDown
- HighLatency
- DeploymentReplicasMismatch

### 4.3 Check AlertManager Configuration

```bash
# Port-forward to AlertManager
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
```

Open: **http://localhost:9093/#/status**

**Expected:** You should see your webhook URL in the configuration.

---

## Step 5: Test Alerting with ArgoCD (10 minutes)

### Important: Disable ArgoCD Auto-Sync

Before testing, you need to disable ArgoCD auto-sync to prevent it from reverting your changes:

```bash
# Disable auto-sync for retail-store-app
argocd app set retail-store-app --sync-policy none

# Or via kubectl
kubectl patch application retail-store-app -n argocd --type merge -p '{"spec":{"syncPolicy":null}}'
```

---

### Test 1: Service Down Alert (2 minutes)

This test triggers an alert when a service has 0 replicas.

```bash
# Scale down the UI service
kubectl scale deployment ui -n retail-store --replicas=0

# Wait 1-2 minutes, then check Prometheus alerts
# Open: http://localhost:9090/alerts
# Expected: "ServiceDown" alert should be FIRING

# Check AlertManager received it
# Open: http://localhost:9093/#/alerts
# Expected: Alert visible in AlertManager

# Check your EC2 webhook endpoint received the alert
# You should see a POST request with alert payload

# Restore the service
kubectl scale deployment ui -n retail-store --replicas=1
```

**Expected Alert Payload:**
```json
{
  "receiver": "aiops-receiver",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "ServiceDown",
        "severity": "critical",
        "namespace": "retail-store",
        "deployment": "ui"
      },
      "annotations": {
        "summary": "Service ui is down",
        "description": "Deployment ui in namespace retail-store has no available replicas."
      }
    }
  ]
}
```

---

### Test 2: Pod Crash Loop Alert (3 minutes)

This test triggers an alert when a pod keeps restarting.

```bash
# Create a pod that will crash repeatedly
kubectl run crash-test -n retail-store --image=busybox --restart=Always -- sh -c "exit 1"

# Wait 2-3 minutes for restarts to accumulate
kubectl get pod crash-test -n retail-store -w

# Check Prometheus alerts
# Open: http://localhost:9090/alerts
# Expected: "PodCrashLooping" alert should be FIRING

# Clean up
kubectl delete pod crash-test -n retail-store
```

---

### Test 3: Deployment Replicas Mismatch Alert (2 minutes)

This test triggers when desired replicas don't match available replicas.

```bash
# Manually delete a pod (simulating a failure)
kubectl delete pod -n retail-store -l app.kubernetes.io/name=catalog

# Immediately check - there will be a brief mismatch
# Open: http://localhost:9090/alerts
# Expected: "DeploymentReplicasMismatch" alert may fire briefly

# The deployment will automatically recreate the pod
kubectl get pods -n retail-store -w
```

---

### Test 4: Verify Webhook Delivery

Check that AlertManager successfully delivered alerts to your EC2 endpoint:

```bash
# Check AlertManager logs for webhook POST requests
kubectl logs -n monitoring alertmanager-kube-prometheus-stack-alertmanager-0 | grep "webhook"

# Expected output:
# level=info msg="Notify success" receiver=aiops-receiver
```

---

### Re-enable ArgoCD Auto-Sync

After testing, re-enable ArgoCD auto-sync:

```bash
# Re-enable auto-sync
argocd app set retail-store-app --sync-policy automated --auto-prune --self-heal

# Or via kubectl
kubectl patch application retail-store-app -n argocd --type merge -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'

# Sync to restore original state
argocd app sync retail-store-app
```

---

## Configured Alerts

Your monitoring stack includes these alerts:

### Critical Alerts (immediate notification)

| Alert | Condition | Threshold |
|-------|-----------|-----------|
| **PodCrashLooping** | Pod restarts repeatedly | >3 restarts in 5 min |
| **ServiceDown** | Service has no replicas | 0 available replicas for 1 min |
| **HighErrorRate** | High 5xx error rate | >5% for 2 min |

### Warning Alerts (grouped notification)

| Alert | Condition | Threshold |
|-------|-----------|-----------|
| **PodNotReady** | Pod not in Running state | Not ready for 5 min |
| **HighCPUUsage** | Container CPU usage high | >80% of limit for 5 min |
| **HighMemoryUsage** | Container memory usage high | >80% of limit for 5 min |
| **HighLatency** | Service response time high | p95 >1s for 5 min |
| **DeploymentReplicasMismatch** | Desired ≠ Available replicas | Mismatch for 5 min |

---

## Access Monitoring UIs

### Prometheus
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
# http://localhost:9090
```

### AlertManager
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
# http://localhost:9093
```

### Grafana
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# http://localhost:3000
# Username: admin
# Password: prom-operator
```

### Loki
```bash
# Access Loki API
kubectl port-forward -n monitoring svc/loki 3100:3100
# http://localhost:3100

# Query logs via API
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="retail-store"}' \
  --data-urlencode 'limit=10'

# Or use Grafana UI (Loki datasource is pre-configured)
# Go to Explore → Select "Loki" datasource → Enter LogQL query
```

---

## Troubleshooting

### Issue: Targets not showing in Prometheus

**Check PodMonitor:**
```bash
kubectl get podmonitors -n monitoring
# Expected: retail-store
```

**Check if pods have Prometheus annotations:**
```bash
kubectl get pod -n retail-store -o yaml | grep prometheus.io
```

### Issue: Targets showing as DOWN

**Check if pods are ready:**
```bash
kubectl get pods -n retail-store
# All should show 1/1 READY
```

**If a pod is not ready, check logs:**
```bash
kubectl logs -n retail-store deployment/<service-name>
kubectl describe pod -n retail-store -l app.kubernetes.io/name=<service-name>
```

**Restart the pod:**
```bash
kubectl delete pod -n retail-store -l app.kubernetes.io/name=<service-name>
```

### Issue: Alerts not firing

**Check if Prometheus is scraping metrics:**
```bash
# Open Prometheus and run this query:
up{namespace="retail-store"}
# Should return 1 for all services
```

**Check alert rules are loaded:**
```bash
kubectl get prometheusrules -n monitoring retail-store-alerts
```

### Issue: Webhook not receiving alerts

**Test connectivity from cluster to EC2:**
```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v -X POST http://YOUR_EC2_IP:5000/alert \
  -H "Content-Type: application/json" \
  -d '{"test": "alert"}'
```

**Check EC2 security group:**
- Ensure inbound rule allows port 5000 from your EKS cluster

**Check AlertManager logs:**
```bash
kubectl logs -n monitoring alertmanager-kube-prometheus-stack-alertmanager-0
```

### Issue: ArgoCD keeps reverting test changes

**Disable auto-sync temporarily:**
```bash
argocd app set retail-store-app --sync-policy none
```

**After testing, re-enable:**
```bash
argocd app set retail-store-app --sync-policy automated --auto-prune --self-heal
```

---

## Quick Reference Commands

```bash
# View all monitoring resources
kubectl get all -n monitoring

# Check Prometheus targets
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
# http://localhost:9090/targets

# Check active alerts
# http://localhost:9090/alerts

# Check AlertManager
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
# http://localhost:9093

# View AlertManager config
kubectl get secret alertmanager-kube-prometheus-stack-alertmanager -n monitoring \
  -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d

# Check alert rules
kubectl get prometheusrules -n monitoring

# Check PodMonitor
kubectl get podmonitors -n monitoring

# View Prometheus logs
kubectl logs -n monitoring prometheus-kube-prometheus-stack-prometheus-0 -c prometheus

# View AlertManager logs
kubectl logs -n monitoring alertmanager-kube-prometheus-stack-alertmanager-0

# Restart Prometheus
kubectl rollout restart statefulset prometheus-kube-prometheus-stack-prometheus -n monitoring

# Restart AlertManager
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring

# Scale service for testing (disable ArgoCD auto-sync first!)
kubectl scale deployment <service-name> -n retail-store --replicas=0

# Restore service
kubectl scale deployment <service-name> -n retail-store --replicas=1
```

---

## What You've Accomplished ✅

- ✅ Prometheus monitoring stack deployed (via Terraform)
- ✅ Loki logging stack deployed (via Terraform)
- ✅ Prometheus scraping all 5 retail-store services
- ✅ Promtail collecting logs from all pods
- ✅ AlertManager configured with webhook to EC2
- ✅ Grafana configured with Prometheus and Loki datasources
- ✅ 8 alert rules configured for various failure scenarios
- ✅ Tested alert firing and webhook delivery
- ✅ Integrated with ArgoCD for GitOps workflow
- ✅ Consistent labels across metrics, logs, and traces for AI correlation

Your AIOps monitoring foundation is ready! 🎉

