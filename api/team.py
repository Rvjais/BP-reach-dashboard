import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from shared import json_handler, error_handler, write_response

API_BASE = "https://api.heyreach.io"


def org_api_call(path, body=None, method="POST"):
    api_key = os.environ.get("HEYREACH_API_KEY", "")
    import urllib.request
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"API error: {e.code} {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            path = urlparse(self.path).path

            if "workspaces" in path and "users" not in path and "keys" not in path:
                data = org_api_call("/api/public/management/organizations/workspaces?Offset=0&Limit=100", method="GET")
            elif "workspace-keys" in path:
                wsid = qs.get("workspaceId", [None])[0]
                if wsid:
                    data = org_api_call(f"/api/public/management/organizations/api-keys/workspaces/{wsid}", method="GET")
                else:
                    data = {"error": "workspaceId required"}
            elif "users" in path and qs.get("userId"):
                uid = qs["userId"][0]
                data = org_api_call(f"/api/public/management/organizations/users/{uid}", method="GET")
            else:
                data = {"error": "Unknown team endpoint"}
            status, headers, body = json_handler(data)
        except Exception as e:
            status, headers, body = error_handler(str(e))
        write_response(self, status, headers, body)

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length)) if content_length else {}
            path = urlparse(self.path).path

            if "invite-admins" in path:
                data = org_api_call("/api/public/management/organizations/users/invite/admins", post_data)
            elif "invite-members" in path:
                data = org_api_call("/api/public/management/organizations/users/invite/members", post_data)
            elif "invite" in path or "invite-managers" in path:
                data = org_api_call("/api/public/management/organizations/users/invite/managers", post_data)
            elif "workspace-create" in path or ("workspaces" in path and "create" in path):
                data = org_api_call("/api/public/management/organizations/workspaces", post_data)
            elif "workspace-update" in path or ("workspaces" in path and "update" in path):
                wsid = post_data.get("workspaceId")
                if wsid:
                    data = org_api_call(f"/api/public/management/organizations/workspaces/{wsid}", post_data, method="PATCH")
                else:
                    data = {"error": "workspaceId required"}
            elif "workspace-keys-create" in path:
                wsid = post_data.get("workspaceId")
                if wsid:
                    data = org_api_call(f"/api/public/management/organizations/api-keys/workspaces/{wsid}", post_data)
                else:
                    data = {"error": "workspaceId required"}
            elif "all-users" in path or ("users" in path and "workspaces" not in path):
                data = org_api_call("/api/public/management/organizations/users", post_data)
            elif "workspace-users" in path:
                wsid = post_data.get("workspaceId") or parse_qs(urlparse(self.path).query).get("workspaceId", [None])[0]
                if wsid:
                    data = org_api_call(f"/api/public/management/organizations/users/workspaces/{wsid}", post_data)
                else:
                    data = {"error": "workspaceId required"}
            else:
                data = {"error": "Unknown team action"}
            status, headers, body = json_handler(data)
        except Exception as e:
            status, headers, body = error_handler(str(e))
        write_response(self, status, headers, body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
