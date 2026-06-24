import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from lib.client import heyreach_post
from lib.util import json_handler, error_handler, write_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            offset = int(qs.get("offset", [0])[0])
            limit = int(qs.get("limit", [20])[0])
            data = heyreach_post(
                "/api/public/inbox/GetConversationsV2",
                {"offset": offset, "limit": limit},
            )
            status, headers, body = json_handler(data)
        except Exception as e:
            status, headers, body = error_handler(str(e))
        write_response(self, status, headers, body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
