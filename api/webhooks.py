import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from shared import heyreach_post, json_handler, error_handler, write_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("webhookId"):
                wid = qs["webhookId"][0]
                data = heyreach_post(
                    f"/api/public/webhooks/GetWebhookById?webhookId={wid}&includeCustomHeaders=false",
                    None
                )
            else:
                data = heyreach_post("/api/public/webhooks/GetAllWebhooks", {"limit": 100, "offset": 0})
            status, headers, body = json_handler(data)
        except Exception as e:
            status, headers, body = error_handler(str(e))
        write_response(self, status, headers, body)

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))
            path = urlparse(self.path).path
            if "create" in path:
                data = heyreach_post("/api/public/webhooks/CreateWebhook", post_data)
            elif "delete" in path:
                wid = post_data.get("webhookId") or post_data.get("id")
                data = heyreach_post(f"/api/public/webhooks/DeleteWebhook?webhookId={wid}", None)
            elif "update" in path:
                data = heyreach_post(f"/api/public/webhooks/UpdateWebhook?webhookId={post_data.get('id')}", post_data)
            else:
                data = {"error": "Unknown webhook action"}
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
