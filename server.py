import http.server
import json
import os
import subprocess
import urllib.parse
from pathlib import Path

HEYREACH_BIN = str(Path.home() / ".local/bin/heyreach")
PORT = 8765

def find_api_key():
    if key := os.environ.get("HEYREACH_API_KEY"):
        return key
    fish_config = Path.home() / ".config" / "fish" / "config.fish"
    if fish_config.exists():
        for line in fish_config.read_text().splitlines():
            if "HEYREACH_API_KEY" in line and "set" in line:
                parts = line.replace("set -x ", "").replace("set ", "").split()
                if len(parts) >= 2:
                    return parts[1]
    return ""

API_KEY = find_api_key()

CLI_TIMEOUT = 30

def run_cli(args):
    env = os.environ.copy()
    env["HEYREACH_API_KEY"] = API_KEY or env.get("HEYREACH_API_KEY", "")
    try:
        result = subprocess.run(
            [HEYREACH_BIN] + args,
            capture_output=True, text=True, env=env, timeout=CLI_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return {"error": "CLI command timed out"}
    except FileNotFoundError:
        return {"error": f"CLI binary not found at {HEYREACH_BIN}"}
    if result.returncode != 0:
        return {"error": result.stderr.strip() or result.stdout.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "Failed to parse CLI output", "raw": result.stdout}


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/campaigns":
            data = run_cli(["campaigns", "list", "--limit", params.get("limit", ["100"])[0]])
            self._json(data)

        elif path == "/api/campaign" and params.get("id"):
            data = run_cli(["campaigns", "list", "--limit", "1000"])
            if "items" in data:
                cid = int(params["id"][0])
                for c in data["items"]:
                    if c["id"] == cid:
                        self._json(c)
                        return
                self._json({"error": "not found"})
            else:
                self._json(data)

        elif path == "/api/lists":
            data = run_cli(["lists", "list", "--limit", params.get("limit", ["100"])[0]])
            self._json(data)

        elif path == "/api/accounts":
            data = run_cli(["li-accounts", "list"])
            self._json(data)

        elif path == "/api/inbox":
            offset = int(params.get("offset", ["0"])[0])
            limit = int(params.get("limit", ["20"])[0])
            body = {"offset": offset, "limit": limit}
            data = run_cli(["inbox", "conversations", "--body", json.dumps(body)])
            self._json(data)

        elif path == "/api/stats/overall":
            data = run_cli(["stats", "overall"])
            self._json(data)

        elif path == "/api/overview":
            campaigns = run_cli(["campaigns", "list", "--limit", "100"])
            lists = run_cli(["lists", "list", "--limit", "100"])
            accounts = run_cli(["li-accounts", "list"])
            inbox = run_cli(["inbox", "conversations", "--body", json.dumps({"offset": 0, "limit": 1})])

            total_campaigns = len(campaigns.get("items", []))
            total_lists = len(lists.get("items", []))
            total_accounts = len(accounts.get("items", []))
            total_leads = sum(l.get("totalItemsCount", 0) for l in lists.get("items", []))
            statuses = {}
            for c in campaigns.get("items", []):
                s = c.get("status", "UNKNOWN")
                statuses[s] = statuses.get(s, 0) + 1
            active = statuses.get("IN_PROGRESS", 0)
            total_inbox = inbox.get("totalCount", 0) if "totalCount" in inbox else 0

            self._json({
                "totalCampaigns": total_campaigns,
                "activeCampaigns": active,
                "totalLists": total_lists,
                "totalAccounts": total_accounts,
                "totalLeads": total_leads,
                "totalInbox": total_inbox,
                "statusBreakdown": statuses,
                "inboxError": "error" in inbox,
            })

        elif path == "/":
            self._serve_file("index.html")

        elif path == "/api/stats/by-campaign":
            data = run_cli(["stats", "by-campaign"])
            if "byDayStats" in data:
                by_campaign = {}
                for day_stats in data["byDayStats"].values():
                    for entry in day_stats:
                        cid = entry.get("campaignId")
                        if cid not in by_campaign:
                            by_campaign[cid] = {**entry}
                            by_campaign[cid]["days"] = 1
                        else:
                            for k, v in entry.items():
                                if isinstance(v, (int, float)) and k not in ("campaignId", "isCampaignDeleted"):
                                    by_campaign[cid][k] = by_campaign[cid].get(k, 0) + v
                            by_campaign[cid]["days"] += 1
                for cid in by_campaign:
                    for k in list(by_campaign[cid].keys()):
                        if k.endswith("Rate"):
                            by_campaign[cid][k] = round(by_campaign[cid].get(k, 0) / max(by_campaign[cid]["days"], 1), 4)
                data = {"items": list(by_campaign.values())}
            self._json(data)

        else:
            static_path = path.lstrip("/")
            full = Path(__file__).parent / static_path
            if full.exists() and full.is_file():
                self._serve_file(str(full))
            else:
                self._serve_file("index.html")

    def _serve_file(self, filename):
        full = Path(__file__).parent / filename
        if not full.exists():
            self.send_error(404)
            return
        ext = full.suffix
        ct = {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(full, "rb") as f:
            self.wfile.write(f.read())

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        msg = format % args
        if "/api/" in msg:
            print(f"[API] {msg}")


if __name__ == "__main__":
    print(f"HeyReach Dashboard: http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
