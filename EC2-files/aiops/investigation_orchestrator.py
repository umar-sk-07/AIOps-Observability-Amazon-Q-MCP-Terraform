import os
import subprocess
import asyncio
import httpx
from datetime import datetime
import re


# ─── Load the Q prompt from file ──────────────────────────────────────────────
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "AMAZON_Q_PROMPT.txt")

def _load_prompt():
    try:
        with open(_PROMPT_PATH, "r") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Warning: could not load prompt file: {e}")
        return ""

BASE_PROMPT = _load_prompt()


class InvestigationOrchestrator:
    def __init__(self):
        self.discord_webhook   = os.getenv("DISCORD_WEBHOOK_URL")
        self.discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        self.cluster_name      = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
        self.aws_region        = os.getenv("AWS_REGION", "ap-south-1")
        self.q_path            = "/home/ec2-user/.local/bin/qchat"

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN FLOW
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_alert(self, alert, inv_record: dict):
        """
        Flow:
          1. Post immediate "investigating" notice to Discord (Python)
          2. Build full prompt = BASE_PROMPT + alert context
          3. Hand off entirely to Q CLI — Q investigates, posts RCA to Discord,
             polls for human reply, executes remediation, posts confirmation
          4. Update inv_record with outcome
        """
        alert_name  = alert.labels.get("alertname", "Unknown")
        namespace   = alert.labels.get("namespace", "default")
        pod         = alert.labels.get("pod", "")
        deployment  = alert.labels.get("deployment", "")
        severity    = alert.labels.get("severity", "unknown")
        description = alert.annotations.get("description", "")
        summary     = alert.annotations.get("summary", "")
        target      = pod or deployment or "N/A"

        print(f"[{datetime.utcnow().isoformat()}] Investigation started: "
              f"{alert_name} | {namespace}/{target} | {severity}")

        # ── Step 1: Immediate Discord notice (Python, not Q) ──────────────────
        await self._post_investigating_notice(
            alert_name, namespace, target, severity, summary
        )

        # ── Step 2: Build the full prompt ─────────────────────────────────────
        alert_context = f"""
---

## Active Alert

You have received the following alert. Begin the workflow from STEP 1.

| Field       | Value                        |
|-------------|------------------------------|
| Alert Name  | {alert_name}                 |
| Severity    | {severity}                   |
| Namespace   | {namespace}                  |
| Target      | {target}                     |
| Summary     | {summary or 'N/A'}           |
| Description | {description or 'N/A'}       |
| Fired At    | {datetime.utcnow().isoformat()} UTC |

EKS Cluster : {self.cluster_name}
AWS Region  : {self.aws_region}
Discord Channel ID: {self.discord_channel_id}
"""
        full_prompt = BASE_PROMPT + alert_context

        # ── Step 3: Hand off to Q CLI ──────────────────────────────────────────
        inv_record["status"] = "q_running"
        result = await self._run_q(full_prompt, alert_name)

        # ── Step 4: Update record ──────────────────────────────────────────────
        inv_record["q_output_preview"] = result.get("output", "")[:500]
        inv_record["status"] = "completed" if result["success"] else "q_error"
        inv_record["remediation_status"] = "completed" if result["success"] else "error"

        print(f"[{datetime.utcnow().isoformat()}] Investigation finished: "
              f"{alert_name} | success={result['success']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Q CLI RUNNER
    # ─────────────────────────────────────────────────────────────────────────

    async def _run_q(self, prompt, alert_name):
        """Run Q CLI non-interactively. Q handles everything: Discord posts,
        polling for human reply, and executing remediation."""

        print(f"  → Handing off to Q CLI for: {alert_name}")

        def _run():
            try:
                r = subprocess.run(
                    [self.q_path, "chat", "-a", "--no-interactive"],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=600,   # 10 min — covers investigation + 5 min wait + remediation
                    env={**os.environ, "HOME": "/home/ec2-user"}
                )
                out = r.stdout.strip() or r.stderr.strip() or "(no output)"
                # Strip ANSI codes for cleaner logs
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                out = ansi_escape.sub('', out)
                out = re.sub(r'\d+m', '', out)
                out = re.sub(r'mm+', '', out)
                out = re.sub(r' +', ' ', out).strip()
                print(f"  → Q CLI finished. Exit={r.returncode}, "
                      f"output={len(out)} chars")
                if out:
                    print(f"  → Q output preview: {out[:300]}")
                return {"success": r.returncode == 0, "output": out}
            except subprocess.TimeoutExpired:
                msg = f"Q CLI timed out after 10 minutes for {alert_name}"
                print(f"  → {msg}")
                return {"success": False, "output": msg}
            except Exception as e:
                msg = f"Q CLI error: {e}"
                print(f"  → {msg}")
                return {"success": False, "output": msg}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)

    # ─────────────────────────────────────────────────────────────────────────
    # DISCORD — IMMEDIATE NOTICE (Python-side only, before Q starts)
    # ─────────────────────────────────────────────────────────────────────────

    async def _post_investigating_notice(self, alert_name, namespace, target,
                                         severity, summary):
        """Post an immediate 'investigating' notice so Discord gets feedback
        right away, before Q CLI even starts loading MCPs."""
        color = 15158332 if severity == "critical" else 16776960
        emoji = "🔴" if severity == "critical" else "🟡"

        embed = {
            "title": f"{emoji} ALERT: {alert_name}",
            "description": (
                "Amazon Q is now investigating using **EKS MCP** and **Discord MCP**.\n"
                "Root Cause Analysis will be posted here shortly."
            ),
            "color": color,
            "fields": [
                {"name": "Namespace", "value": f"`{namespace}`",       "inline": True},
                {"name": "Target",    "value": f"`{target}`",          "inline": True},
                {"name": "Severity",  "value": severity.upper(),        "inline": True},
                {"name": "Summary",   "value": summary or "See description",
                 "inline": False},
                {"name": "Status",    "value": "⏳ Q CLI loading MCP tools...",
                 "inline": False},
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.post(
                    self.discord_webhook,
                    json={"embeds": [embed]},
                    params={"wait": "true"}
                )
                msg_id = r.json().get("id")
                print(f"  → Investigating notice posted to Discord (id={msg_id})")
                return msg_id
            except Exception as e:
                print(f"  → Failed to post investigating notice: {e}")
                return None
