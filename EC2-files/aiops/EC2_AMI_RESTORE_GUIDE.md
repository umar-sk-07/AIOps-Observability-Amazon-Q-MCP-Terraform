# EC2 AMI Restore Guide — After Infrastructure Rebuild

You are using **2 MCPs only: EKS MCP and Discord MCP.**

Neither MCP connects to any URL you need to manage.
The only thing that changes after a rebuild is the kubeconfig and the EC2 private IP.

---

## How each MCP connects (so you understand what can change)

### EKS MCP (`awslabs.eks-mcp-server`)
```json
"env": { "AWS_REGION": "ap-south-1" }
```
- Connects to AWS APIs using the **EC2 instance IAM role** — no credentials to update
- Discovers the cluster via **`~/.kube/config`** — this is the only thing that changes
- `AWS_REGION` is `ap-south-1` — stays the same unless you move regions

### Discord MCP (`barryy625/mcp-discord`)
```json
"-e", "DISCORD_TOKEN=MTUwMjY4..."
```
- Connects to Discord API using the **bot token baked into the docker run args**
- The token is tied to your Discord bot, not to AWS — **never changes after a rebuild**
- No URLs, no cluster references, nothing to update

---

## What changes after rebuild ⚠️

| What | Why | Where |
|------|-----|-------|
| `~/.kube/config` | Points to old cluster endpoint | Regenerate with one command |
| `EKS_CLUSTER_NAME` in `.env` | Old cluster name in the env var | Edit one line |
| EC2 private IP | May shift in subnet | Update alertmanager-config.yaml in repo |

That's it. Nothing in `~/.aws/amazonq/mcp.json` needs touching.

---

## Steps after rebuild — in order

### 1. Get the new cluster name

```bash
aws eks list-clusters --region ap-south-1 --query "clusters" --output text
```

---

### 2. Regenerate kubeconfig

```bash
aws eks update-kubeconfig --name <NEW_CLUSTER_NAME> --region ap-south-1
```

Verify:

```bash
kubectl get nodes
kubectl get pods -n retail-store
```

---

### 3. Update `.env`

```bash
nano ~/aiops/.env
```

Change one line:

```
EKS_CLUSTER_NAME=retail-store-pk7w    ← old, stale
EKS_CLUSTER_NAME=<NEW_CLUSTER_NAME>   ← new
```

Everything else in `.env` stays the same (Discord tokens, region, etc).

---

### 4. Check if EC2 private IP changed

```bash
curl -s http://169.254.169.254/latest/meta-data/local-ipv4
```

If it is **still `10.0.0.70`** → nothing to do.

If it **changed** → update `monitoring/alertmanager-config.yaml` in your repo:

```yaml
receivers:
  - name: 'aiops-receiver'
    webhook_configs:
      - url: 'http://<NEW_EC2_PRIVATE_IP>:5000/alert'   # ← update this
```

Then apply to the new cluster:

```bash
kubectl apply -f monitoring/alertmanager-config.yaml
kubectl rollout restart statefulset \
  alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

---

### 5. Apply monitoring stack to new cluster

Run from your local machine in the repo root:

```bash
kubectl apply -f monitoring/prometheus-rules.yaml
kubectl apply -f monitoring/alertmanager-config.yaml
kubectl apply -f monitoring/podmonitor.yaml
```

---

### 6. Restart the webhook service

```bash
sudo systemctl restart aiops-webhook
curl http://localhost:5000/health
```

---

### 7. Test end-to-end

```bash
# Trigger a ServiceDown alert
kubectl scale deployment ui -n retail-store --replicas=0

# Open dashboard
# http://<EC2_PUBLIC_IP>

# Restore after confirming alert received in Discord
kubectl scale deployment ui -n retail-store --replicas=1
```

---

## Before creating an AMI — always do this first

The Discord bot token in `~/.aws/amazonq/mcp.json` must match the one in `~/aiops/.env`.
They can drift if the token was regenerated. Run this before snapshotting:

```bash
# Verify both match
grep DISCORD_BOT_TOKEN ~/aiops/.env
grep DISCORD_TOKEN ~/.aws/amazonq/mcp.json
# The token value after the = should be identical in both lines
```

If they differ, update `mcp.json` manually:
```bash
nano ~/.aws/amazonq/mcp.json
# Find the DISCORD_TOKEN= line and paste the value from .env
```

---

## What does NOT need updating after rebuild

| Item | Reason |
|------|--------|
| `~/.aws/amazonq/mcp.json` | EKS MCP uses IAM role + kubeconfig, Discord MCP uses baked-in bot token — no URLs |
| Discord bot token | Tied to your Discord app, not to AWS |
| Discord webhook URL | Tied to your Discord server, not to AWS |
| Discord channel ID | Tied to your Discord server, not to AWS |
| nginx config | Just proxies port 80 → 5000, no cluster references |
| systemd service | No cluster references |
| Python code | Reads cluster name from `.env` at runtime |
| Amazon Q login | Builder ID auth, not cluster-specific |
| AWS region | Staying in `ap-south-1` |

---

## Current values (stale after rebuild — for reference only)

```
EKS Cluster Name : retail-store-pk7w
EKS API Endpoint : https://C4DF4304A17BABCF453AB027EB8BB1C1.gr7.ap-south-1.eks.amazonaws.com
EC2 Private IP   : 10.0.0.70
EC2 Public IP    : 52.66.202.50
AWS Account ID   : 704593925808
AWS Region       : ap-south-1  ← stays the same
```

---

*Last updated: May 10, 2026*
