# Quick Start Guide - Prometheus Alerting Setup

Follow these steps to get your monitoring and alerting system up and running.

## Step-by-Step Setup

### 1. Enable Monitoring Stack (5 minutes)

```bash
cd terraform

# Apply with monitoring enabled
terraform apply -var="enable_monitoring=true"

# Or update your terraform.tfvars file:
echo 'enable_monitoring = true' >> terraform.tfvars
terraform apply
```

Wait for the monitoring stack to be deployed. This installs:
- ✅ Prometheus Server
- ✅ AlertManager
- ✅ Grafana
- ✅ Node Exporter
- ✅ Kube State Metrics

### 2. Verify Monitoring Stack (2 minutes)

```bash
# Check all monitoring pods are running
kubectl get pods -n monitoring

# You should see pods like:
# - prometheus-kube-prometheus-stack-prometheus-0
# - alertmanager-kube-prometheus-stack-alertmanager-0
# - kube-prometheus-stack-grafana-xxx
# - kube-prometheus-stack-operator-xxx
# - kube-state-metrics-xxx
# - prometheus-node-exporter-xxx

# Wait until all pods show STATUS: Running
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=kube-prometheus-stack -n monitoring --timeout=300s
```

### 3. Update AlertManager with Your EC2 IP (1 minute)

```bash
# Replace <EC2_IP> with your actual EC2 instance IP address
sed -i 's/<EC2_IP>/YOUR_ACTUAL_IP/g' monitoring/alertmanager-config.yaml

# For example:
# sed -i 's/<EC2_IP>/54.123.45.67/g' monitoring/alertmanager-config.yaml
```

### 4. Deploy Prometheus Rules (1 minute)

```bash
# Apply the alerting rules
kubectl apply -f monitoring/prometheus-rules.yaml

# Verify rules are created
kubectl get prometheusrules -n monitoring
```

### 5. Deploy AlertManager Configuration (1 minute)

```bash
# Apply AlertManager config
kubectl apply -f monitoring/alertmanager-config.yaml

# Restart AlertManager to pick up the new configuration
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring

# Wait for restart to complete
kubectl rollout status statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

### 6. Verify Everything is Working (2 minutes)

#### Check Prometheus Rules

```bash
# Port-forward to Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090 &

# Open in browser: http://localhost:9090/rules
# You should see "retail-store-alerts" with all your rules
```

#### Check AlertManager Configuration

```bash
# Port-forward to AlertManager
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093 &

# Open in browser: http://localhost:9093
# Go to Status -> Config
# Verify you see your webhook URL with your EC2 IP
```

#### Check Prometheus Targets

```bash
# In Prometheus UI: http://localhost:9090/targets
# Verify your retail-store services are being scraped
# Look for targets with namespace="retail-store"
```

### 7. Test Alert Flow (5 minutes)

#### Test 1: Trigger a Pod Crash Loop Alert

```bash
# Create a pod that will crash
kubectl run crash-test -n retail-store --image=busybox --restart=Always -- sh -c "exit 1"

# Wait 2-3 minutes, then check Prometheus alerts
# http://localhost:9090/alerts
# You should see "PodCrashLooping" alert firing

# Check AlertManager received it
# http://localhost:9093/#/alerts

# Clean up
kubectl delete pod crash-test -n retail-store
```

#### Test 2: Trigger Service Down Alert

```bash
# Scale down a service
kubectl scale deployment ui -n retail-store --replicas=0

# Wait 1-2 minutes, check alerts
# http://localhost:9090/alerts
# You should see "ServiceDown" alert firing

# Restore service
kubectl scale deployment ui -n retail-store --replicas=1
```

#### Test 3: Verify Webhook Delivery

```bash
# Check AlertManager logs for webhook POST requests
kubectl logs -n monitoring alertmanager-kube-prometheus-stack-alertmanager-0 | grep "webhook"

# You should see lines like:
# level=info msg="Notify success" receiver=aiops-receiver
```

## What You've Accomplished ✅

- ✅ Prometheus is scraping metrics from all 5 retail-store services
- ✅ AlertManager is configured with your webhook receiver
- ✅ Alerts are configured for:
  - Pod crash looping (>3 restarts in 5 min)
  - High CPU usage (>80%)
  - High error rate (>5% 5xx errors)
  - Service down (0 replicas)
  - High memory usage (>80%)
  - High latency (p95 >1s)

## Access Your Monitoring UIs

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

## Alert Webhook Payload

Your EC2 endpoint will receive POST requests like this:

```json
{
  "receiver": "aiops-receiver",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "PodCrashLooping",
        "severity": "critical",
        "namespace": "retail-store",
        "pod": "cart-7d8f9c5b6d-abc12"
      },
      "annotations": {
        "summary": "Pod retail-store/cart-7d8f9c5b6d-abc12 is crash looping",
        "description": "Pod cart-7d8f9c5b6d-abc12 has restarted 4 times in the last 5 minutes."
      },
      "startsAt": "2026-05-08T10:30:00.000Z"
    }
  ]
}
```

## Troubleshooting

### Issue: Alerts not firing

**Solution**: Check if Prometheus is scraping your services
```bash
# Visit http://localhost:9090/targets
# Look for retail-store namespace targets
# If missing, your pods need Prometheus annotations
```

### Issue: Webhook not receiving alerts

**Solution 1**: Check AlertManager logs
```bash
kubectl logs -n monitoring alertmanager-kube-prometheus-stack-alertmanager-0
```

**Solution 2**: Verify EC2 security group allows inbound on port 5000

**Solution 3**: Test connectivity from cluster
```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://YOUR_EC2_IP:5000/alert
```

### Issue: Prometheus not scraping application metrics

**Solution**: Add annotations to your service deployments

For each service (ui, cart, catalog, checkout, orders), ensure the deployment has:

```yaml
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/actuator/prometheus"
```

## Next Steps

1. **Set up your AIOps receiver** on EC2 to handle incoming alerts
2. **Customize alert thresholds** in `monitoring/prometheus-rules.yaml`
3. **Add Grafana dashboards** for visualization
4. **Configure alert silences** for maintenance windows
5. **Add more receivers** (Slack, PagerDuty) for different alert severities

## Need Help?

See the full documentation in `monitoring/README.md` for:
- Detailed troubleshooting
- Alert customization
- Adding more receivers
- Metrics reference
- Advanced configurations
