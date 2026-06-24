import os
from http.server import BaseHTTPRequestHandler
from lib.util import json_handler, write_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        has_key = bool(os.environ.get("HEYREACH_API_KEY"))
        data = {
            "status": "ok",
            "apiKeyConfigured": has_key,
        }
        write_response(self, *json_handler(data))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
