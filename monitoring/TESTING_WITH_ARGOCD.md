# Testing Alerts with ArgoCD Running

This guide shows how to safely test your Prometheus alerts without ArgoCD interference.

## Understanding ArgoCD Behavior

Your ArgoCD setup:
- **Manages**: `retail-store` namespace
- **Source**: Git repository Helm chart
- **Auto-sync**: Enabled with `prune: true` and `selfHeal: true`
- **Sync interval**: ~3 minutes

**Important**: ArgoCD will revert any manual changes to resources it manages within ~3 minutes.

## Safe Testing Methods

### Method 1: Temporary Test Pods ✅ (Recommended)

Create pods that ArgoCD doesn't know about:

```bash
# Test 1: Pod Crash Loop Alert
kubectl run crash-test -n retail-store \
  --image=busybox \
  --restart=Always \
  -- sh -c "exit 1"

# Wait 2-3 minutes, check alert fires
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
# Visit http://localhost:9090/alerts

# Clean up
kubectl delete pod crash-test -n retail-store
```

```bash
# Test 2: High CPU Alert
kubectl run cpu-stress -n retail-store \
  --image=polinux/stress \
  --restart=Never \
  -- stress --cpu 2 --timeout 300s

# Wait 5 minutes, check alert fires

# Clean up (auto-deletes after 300s)
kubectl delete pod cpu-stress -n retail-store --ignore-not-found
```

```bash
# Test 3: High Memory Alert
kubectl run memory-stress -n retail-store \
  --image=polinux/stress \
  --restart=Never \
  -- stress --vm 1 --vm-bytes 512M --timeout 300s

# Wait 5 minutes, check alert fires

# Clean up
kubectl delete pod memory-stress -n retail-store --ignore-not-found
```

**Why this works**: ArgoCD only manages resources defined in Git. These test pods aren't in Git, so ArgoCD ignores them.

### Method 2: Temporarily Disable Auto-Sync ⚠️

Use this when you need to test by modifying existing deployments:

```bash
# Step 1: Disable auto-sync
kubectl patch application retail-store-app -n argocd \
  --type=merge \
  -p='{"spec":{"syncPolicy":{"automated":null}}}'

# Verify auto-sync is disabled
kubectl get application retail-store-app -n argocd -o jsonpath='{.spec.syncPolicy}'

# Step 2: Test ServiceDown alert by scaling
kubectl scale deployment ui -n retail-store --replicas=0

# Wait 1-2 minutes, check alert fires
# http://localhost:9090/alerts

# Step 3: Restore the deployment
kubectl scale deployment ui -n retail-store --replicas=1

# Step 4: Re-enable auto-sync
kubectl patch application retail-store-app -n argocd \
  --type=merge \
  -p='{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'

# Verify auto-sync is enabled
kubectl get application retail-store-app -n argocd -o jsonpath='{.spec.syncPolicy}'
```

### Method 3: Separate Test Namespace ✅ (Best for Extensive Testing)

Create a completely separate namespace for testing:

```bash
# Step 1: Create test namespace
kubectl create namespace retail-store-test

# Step 2: Deploy a simple test application
kubectl create deployment test-app -n retail-store-test --image=nginx --replicas=2

# Step 3: Expose it as a service
kubectl expose deployment test-app -n retail-store-test --port=80

# Step 4: Add Prometheus scrape annotations
kubectl patch deployment test-app -n retail-store-test -p '
{
  "spec": {
    "template": {
      "metadata": {
        "annotations": {
          "prometheus.io/scrape": "true",
          "prometheus.io/port": "80",
          "prometheus.io/path": "/metrics"
        }
      }
    }
  }
}'

# Now test various scenarios:

# Test ServiceDown
kubectl scale deployment test-app -n retail-store-test --replicas=0
# Wait 1 minute, check alert

# Test DeploymentReplicasMismatch
kubectl scale deployment test-app -n retail-store-test --replicas=3
kubectl delete pod -n retail-store-test -l app=test-app --force --grace-period=0
# Wait 5 minutes, check alert

# Clean up when done
kubectl delete namespace retail-store-test
```

## Monitoring Stack Deployment (No ArgoCD Conflict)

The monitoring stack is completely safe to deploy:

```bash
# Step 1: Enable monitoring via Terraform
cd terraform
terraform apply -var="enable_monitoring=true"

# Step 2: Wait for monitoring pods
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/instance=kube-prometheus-stack \
  -n monitoring --timeout=300s

# Step 3: Deploy Prometheus rules
kubectl apply -f monitoring/prometheus-rules.yaml

# Step 4: Update AlertManager config (replace <EC2_IP> first!)
kubectl apply -f monitoring/alertmanager-config.yaml

# Step 5: Restart AlertManager
kubectl rollout restart statefulset \
  alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

**Why no conflict**: 
- Monitoring uses `monitoring` namespace
- ArgoCD only has permissions for `retail-store` namespace
- Terraform manages the monitoring stack, not ArgoCD

## What Happens If ArgoCD Interferes?

### Scenario: You scale a deployment manually

```bash
# You do this:
kubectl scale deployment cart -n retail-store --replicas=0

# ArgoCD detects drift within ~3 minutes
# ArgoCD syncs from Git and restores replicas to original value
# Your ServiceDown alert fires briefly, then resolves
```

### How to Check ArgoCD Status

```bash
# Check if ArgoCD is syncing
kubectl get application retail-store-app -n argocd

# Watch ArgoCD sync activity
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller -f

# Check last sync time
kubectl get application retail-store-app -n argocd -o jsonpath='{.status.sync.syncedAt}'
```

## Recommended Testing Sequence

### Phase 1: Monitoring Stack Setup (No ArgoCD Impact)
```bash
# 1. Enable monitoring
cd terraform && terraform apply -var="enable_monitoring=true"

# 2. Verify monitoring pods
kubectl get pods -n monitoring

# 3. Deploy alert rules
kubectl apply -f monitoring/prometheus-rules.yaml
kubectl apply -f monitoring/alertmanager-config.yaml

# 4. Restart AlertManager
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

### Phase 2: Test with Temporary Pods (No ArgoCD Impact)
```bash
# Test 1: Crash loop
kubectl run crash-test -n retail-store --image=busybox --restart=Always -- sh -c "exit 1"
# Wait 2 min, verify alert, then: kubectl delete pod crash-test -n retail-store

# Test 2: CPU stress
kubectl run cpu-stress -n retail-store --image=polinux/stress --restart=Never -- stress --cpu 2 --timeout 300s
# Wait 5 min, verify alert

# Test 3: Check webhook delivery
kubectl logs -n monitoring alertmanager-kube-prometheus-stack-alertmanager-0 | grep webhook
```

### Phase 3: Test with Existing Services (Disable ArgoCD First)
```bash
# 1. Disable auto-sync
kubectl patch application retail-store-app -n argocd --type=merge -p='{"spec":{"syncPolicy":{"automated":null}}}'

# 2. Test ServiceDown
kubectl scale deployment ui -n retail-store --replicas=0
# Wait 1 min, verify alert

# 3. Restore
kubectl scale deployment ui -n retail-store --replicas=1

# 4. Re-enable auto-sync
kubectl patch application retail-store-app -n argocd --type=merge -p='{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'
```

## Troubleshooting

### Issue: ArgoCD keeps reverting my changes

**Cause**: Auto-sync is enabled and you're modifying resources ArgoCD manages.

**Solution**: Use Method 1 (temporary test pods) or Method 2 (disable auto-sync temporarily).

### Issue: Test pod not triggering alerts

**Cause**: Prometheus might not be scraping the test pod.

**Solution**: Check Prometheus targets:
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
# Visit http://localhost:9090/targets
# Look for your test pod
```

### Issue: ArgoCD shows "OutOfSync"

**Cause**: You made manual changes to managed resources.

**Solution**: Either:
1. Let ArgoCD auto-sync (wait 3 minutes)
2. Manually sync: `kubectl patch application retail-store-app -n argocd -p '{"operation":{"sync":{}}}' --type=merge`
3. Revert your changes: `kubectl rollout undo deployment <name> -n retail-store`

## Best Practices

1. ✅ **Use temporary test pods** for most testing
2. ✅ **Use separate namespace** for extensive testing
3. ✅ **Disable auto-sync** only when necessary
4. ✅ **Re-enable auto-sync** immediately after testing
5. ✅ **Clean up test resources** when done
6. ❌ **Don't modify** ArgoCD-managed resources without disabling auto-sync
7. ❌ **Don't leave** auto-sync disabled for extended periods

## Quick Reference

### Check ArgoCD Status
```bash
kubectl get application retail-store-app -n argocd
```

### Disable Auto-Sync
```bash
kubectl patch application retail-store-app -n argocd --type=merge -p='{"spec":{"syncPolicy":{"automated":null}}}'
```

### Enable Auto-Sync
```bash
kubectl patch application retail-store-app -n argocd --type=merge -p='{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'
```

### Force Sync
```bash
kubectl patch application retail-store-app -n argocd -p '{"operation":{"sync":{}}}' --type=merge
```

### Check Monitoring Stack
```bash
kubectl get pods -n monitoring
kubectl get prometheusrules -n monitoring
kubectl get alertmanager -n monitoring
```

## Summary

- ✅ **Monitoring namespace**: Completely safe, ArgoCD won't touch it
- ✅ **Temporary test pods**: Safe, ArgoCD ignores them
- ⚠️ **Modifying existing deployments**: ArgoCD will revert within ~3 minutes
- ✅ **Separate test namespace**: Best for extensive testing without conflicts

**Recommended approach**: Use temporary test pods (Method 1) for quick validation, then monitor real application behavior in production.
