from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import httpx

load_dotenv("/home/ec2-user/aiops/.env")

app = FastAPI(title="AIOps Incident Response", version="3.0.0")

alerts_store        = []
investigations_store = []

# ─── Models ───────────────────────────────────────────────────────────────────

class Alert(BaseModel):
    status: str
    labels: dict = {}
    annotations: dict = {}
    startsAt: str = ""
    endsAt: Optional[str] = None
    fingerprint: Optional[str] = None

class AlertManagerWebhook(BaseModel):
    receiver: str = "aiops-receiver"
    status: str
    alerts: List[Alert] = []

# ─── GUI ──────────────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIOps Dashboard</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#c9d1d9}
    .header{background:linear-gradient(135deg,#161b22,#21262d);padding:18px 28px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:14px}
    .header h1{font-size:1.5rem;color:#58a6ff}
    .dot{width:11px;height:11px;border-radius:50%;background:#3fb950;box-shadow:0 0 8px #3fb950;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    .hright{margin-left:auto;display:flex;gap:10px;align-items:center}
    .badge-ec2{background:#21262d;border:1px solid #30363d;color:#8b949e;padding:5px 12px;border-radius:6px;font-size:.8rem}
    .btn{padding:7px 14px;border-radius:6px;cursor:pointer;font-size:.82rem;border:1px solid;transition:.15s}
    .btn-refresh{background:#21262d;border-color:#30363d;color:#c9d1d9}
    .btn-refresh:hover{background:#30363d}
    .btn-clear{background:#2d1a1a;border-color:#f85149;color:#f85149}
    .btn-clear:hover{background:#3d1a1a}
    .btn-clear-inv{background:#1a1a2d;border-color:#58a6ff;color:#58a6ff}
    .btn-clear-inv:hover{background:#1a2040}
    .container{max-width:1400px;margin:0 auto;padding:20px}
    .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
    .stat{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;text-align:center}
    .stat .n{font-size:2.4rem;font-weight:700}
    .stat .l{color:#8b949e;font-size:.82rem;margin-top:4px}
    .stat.total .n{color:#58a6ff}
    .stat.crit  .n{color:#f85149}
    .stat.warn  .n{color:#d29922}
    .stat.res   .n{color:#3fb950}
    .section{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;margin-bottom:18px}
    .sec-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
    .sec-header h2{color:#58a6ff;font-size:1.05rem}
    table{width:100%;border-collapse:collapse}
    th{background:#21262d;padding:9px 12px;text-align:left;font-size:.78rem;color:#8b949e;text-transform:uppercase;letter-spacing:.4px}
    td{padding:9px 12px;border-bottom:1px solid #21262d;font-size:.88rem;vertical-align:top}
    tr:hover td{background:#1c2128}
    .b{padding:3px 9px;border-radius:20px;font-size:.73rem;font-weight:600;white-space:nowrap}
    .b.critical{background:#3d1a1a;color:#f85149;border:1px solid #f85149}
    .b.warning{background:#2d2008;color:#d29922;border:1px solid #d29922}
    .b.firing{background:#3d1a1a;color:#f85149}
    .b.resolved{background:#0d2818;color:#3fb950}
    .b.investigating,.b.running_q_investigation{background:#0d1f3c;color:#58a6ff}
    .b.waiting_for_human{background:#2d1a3d;color:#bc8cff}
    .b.remediating{background:#1a2d1a;color:#3fb950}
    .b.completed{background:#0d2818;color:#3fb950}
    .b.declined_or_timeout{background:#21262d;color:#8b949e}
    .b.parse_error{background:#2d2008;color:#d29922}
    .empty{text-align:center;color:#8b949e;padding:36px;font-size:.88rem}
    .rca-cell{max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8rem;color:#8b949e;cursor:pointer}
    .rca-cell:hover{white-space:normal;color:#c9d1d9}
    .arch{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px;font-family:monospace;font-size:.78rem;color:#8b949e;white-space:pre;overflow-x:auto;line-height:1.6}
    .arch .hl{color:#58a6ff}
    .arch .ar{color:#3fb950}
    .footer{text-align:center;color:#8b949e;font-size:.78rem;padding:18px}
    .toast{position:fixed;bottom:24px;right:24px;background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:12px 20px;border-radius:8px;font-size:.85rem;opacity:0;transition:opacity .3s;pointer-events:none;z-index:999}
    .toast.show{opacity:1}
  </style>
</head>
<body>
<div class="header">
  <div class="dot"></div>
  <h1>&#x1F916; AIOps Incident Response</h1>
  <div class="hright">
    <span class="badge-ec2">10.0.0.70:5000 &nbsp;|&nbsp; retail-store only</span>
    <button class="btn btn-refresh" onclick="loadData()">&#x21BB; Refresh</button>
  </div>
</div>

<div class="container">
  <div class="stats">
    <div class="stat total"><div class="n" id="s-total">-</div><div class="l">Total Alerts</div></div>
    <div class="stat crit"><div class="n" id="s-crit">-</div><div class="l">Critical</div></div>
    <div class="stat warn"><div class="n" id="s-warn">-</div><div class="l">Warning</div></div>
    <div class="stat res"><div class="n" id="s-res">-</div><div class="l">Resolved</div></div>
  </div>

  <div class="section">
    <div class="sec-header">
      <h2>&#x1F6A8; Live Alerts</h2>
      <button class="btn btn-clear" onclick="clearAlerts()">&#x1F5D1; Clear Alerts</button>
    </div>
    <div id="alerts-table"><div class="empty">Waiting for AlertManager webhooks from retail-store namespace...</div></div>
  </div>

  <div class="section">
    <div class="sec-header">
      <h2>&#x1F50D; Investigation Log</h2>
      <button class="btn btn-clear-inv" onclick="clearInvestigations()">&#x1F5D1; Clear Log</button>
    </div>
    <div id="inv-table"><div class="empty">No investigations yet.</div></div>
  </div>

  <div class="section">
    <div class="sec-header"><h2>&#x1F3D7; Architecture</h2></div>
    <div class="arch"><span class="hl">AlertManager</span> <span class="ar">&#x2192;</span> <span class="hl">FastAPI :5000</span> (retail-store namespace only)
         <span class="ar">&#x2193;</span>
<span class="hl">Investigation Orchestrator</span>
         <span class="ar">&#x2193;</span>
<span class="hl">Amazon Q CLI</span> <span class="ar">&#x2192;</span> ALL 5 MCPs in parallel:
  <span class="hl">EKS MCP</span>        pod status / events / logs
  <span class="hl">Prometheus MCP</span> CPU / memory / error rate metrics
  <span class="hl">Loki MCP</span>       application log analysis
  <span class="hl">ArgoCD MCP</span>     deployment sync state
  <span class="hl">Discord MCP</span>    post RCA + read human reply
         <span class="ar">&#x2193;</span>
<span class="hl">Discord</span>: Root Cause + 3 specific remediation options
         <span class="ar">&#x2193;</span>
Human replies <span class="hl">1</span> / <span class="hl">2</span> / <span class="hl">3</span> / <span class="hl">no</span>
         <span class="ar">&#x2193;</span>
<span class="hl">Q executes chosen remediation via EKS MCP</span>
         <span class="ar">&#x2193;</span>
<span class="hl">Confirmation posted to Discord</span></div>
  </div>
</div>

<div class="footer">AIOps &bull; EKS: retail-store-wdoc &bull; ap-south-1 &bull; <span id="last-refresh">-</span></div>
<div class="toast" id="toast"></div>

<script>
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

async function clearAlerts() {
  if (!confirm('Clear all alerts from the dashboard?')) return;
  await fetch('/api/alerts/clear', {method:'POST'});
  showToast('Alerts cleared');
  loadData();
}

async function clearInvestigations() {
  if (!confirm('Clear investigation log?')) return;
  await fetch('/api/investigations/clear', {method:'POST'});
  showToast('Investigation log cleared');
  loadData();
}

async function loadData() {
  try {
    const [ar, ir] = await Promise.all([fetch('/api/alerts'), fetch('/api/investigations')]);
    const alerts = await ar.json();
    const invs   = await ir.json();

    document.getElementById('s-total').textContent = alerts.length;
    document.getElementById('s-crit').textContent  = alerts.filter(a => a.labels?.severity === 'critical').length;
    document.getElementById('s-warn').textContent  = alerts.filter(a => a.labels?.severity === 'warning').length;
    document.getElementById('s-res').textContent   = alerts.filter(a => a.status === 'resolved').length;
    document.getElementById('last-refresh').textContent = 'Last refresh: ' + new Date().toLocaleTimeString();

    // Alerts table
    if (!alerts.length) {
      document.getElementById('alerts-table').innerHTML = '<div class="empty">No alerts yet. Trigger one from the monitoring/README.md test steps.</div>';
    } else {
      let h = '<table><thead><tr><th>Alert</th><th>Severity</th><th>Status</th><th>Namespace</th><th>Pod / Deployment</th><th>Received</th></tr></thead><tbody>';
      [...alerts].reverse().forEach(a => {
        const sev = a.labels?.severity || 'unknown';
        const tgt = a.labels?.pod || a.labels?.deployment || '-';
        h += `<tr>
          <td><strong>${a.labels?.alertname || 'Unknown'}</strong></td>
          <td><span class="b ${sev}">${sev}</span></td>
          <td><span class="b ${a.status}">${a.status}</span></td>
          <td><code>${a.labels?.namespace || '-'}</code></td>
          <td><code>${tgt}</code></td>
          <td>${a.received_at || '-'}</td>
        </tr>`;
      });
      h += '</tbody></table>';
      document.getElementById('alerts-table').innerHTML = h;
    }

    // Investigations table
    if (!invs.length) {
      document.getElementById('inv-table').innerHTML = '<div class="empty">No investigations yet.</div>';
    } else {
      let h = '<table><thead><tr><th>Alert</th><th>Status</th><th>Root Cause (hover)</th><th>Discord</th><th>Choice</th><th>Remediation</th><th>Started</th></tr></thead><tbody>';
      [...invs].reverse().forEach(i => {
        const rc = i.root_cause || '-';
        h += `<tr>
          <td><strong>${i.alert_name || '-'}</strong></td>
          <td><span class="b ${(i.status||'').replace(/[^a-z_]/g,'')}">${i.status || '-'}</span></td>
          <td class="rca-cell" title="${rc.replace(/"/g,'&quot;')}">${rc.substring(0,80)}${rc.length>80?'…':''}</td>
          <td>${i.discord_message_id ? '&#x2705; Posted' : '&#x23F3;'}</td>
          <td>${i.user_choice ? 'Option ' + i.user_choice : (i.status === 'waiting_for_human' ? '&#x23F3; Waiting' : '-')}</td>
          <td>${i.remediation_status ? '<span class="b ' + (i.remediation_status==='success'?'completed':'firing') + '">' + i.remediation_status + '</span>' : '-'}</td>
          <td>${i.started_at || '-'}</td>
        </tr>`;
      });
      h += '</tbody></table>';
      document.getElementById('inv-table').innerHTML = h;
    }
  } catch(e) {
    console.error('loadData error:', e);
  }
}

loadData();
setInterval(loadData, 8000);
</script>
</body>
</html>"""


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    import subprocess
    cluster_name = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    html = DASHBOARD_HTML.replace("retail-store-wdoc", cluster_name)
    return HTMLResponse(content=html)


@app.post("/alert")
async def receive_alert(request: Request, background_tasks: BackgroundTasks):
    try:
        body    = await request.json()
        webhook = AlertManagerWebhook(**body)

        for alert in webhook.alerts:
            # Only process retail-store namespace
            ns = alert.labels.get("namespace", "")
            if ns != "retail-store":
                print(f"Ignored alert from namespace '{ns}' (not retail-store)")
                continue

            record = {
                "status":      alert.status,
                "labels":      alert.labels,
                "annotations": alert.annotations,
                "startsAt":    alert.startsAt,
                "received_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "fingerprint": alert.fingerprint,
            }
            alerts_store.append(record)
            print(f"[{datetime.utcnow().isoformat()}] Alert received: {alert.labels.get('alertname')} | {ns} | {alert.status}")

            if alert.status == "firing":
                background_tasks.add_task(_investigate, alert)

        return {"status": "received", "count": len(webhook.alerts)}

    except Exception as e:
        print(f"Webhook parse error: {e}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=200)


@app.get("/api/alerts")
async def get_alerts():
    return alerts_store[-200:]


@app.get("/api/investigations")
async def get_investigations():
    return investigations_store[-100:]


@app.post("/api/alerts/clear")
async def clear_alerts():
    alerts_store.clear()
    return {"status": "cleared"}


@app.post("/api/investigations/clear")
async def clear_investigations():
    investigations_store.clear()
    return {"status": "cleared"}


@app.get("/health")
async def health():
    return {
        "status":         "healthy",
        "timestamp":      datetime.utcnow().isoformat(),
        "alerts":         len(alerts_store),
        "investigations": len(investigations_store),
    }


# ─── Background task ──────────────────────────────────────────────────────────

async def _investigate(alert: Alert):
    from investigation_orchestrator import InvestigationOrchestrator

    inv = {
        "alert_name":          alert.labels.get("alertname", "Unknown"),
        "namespace":           alert.labels.get("namespace", "default"),
        "pod":                 alert.labels.get("pod", ""),
        "status":              "investigating",
        "root_cause":          None,
        "discord_message_id":  None,
        "user_choice":         None,
        "remediation_status":  None,
        "started_at":          datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    investigations_store.append(inv)

    try:
        orch = InvestigationOrchestrator()
        await orch.handle_alert(alert, inv)
    except Exception as e:
        inv["status"] = f"error: {e}"
        print(f"Investigation error: {e}")


if __name__ == "__main__":
    import uvicorn
    print("Starting AIOps Webhook Receiver on 0.0.0.0:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
