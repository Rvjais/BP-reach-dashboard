import json
from http.server import BaseHTTPRequestHandler
from _client import heyreach_post
from _util import json_handler, error_handler, write_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = heyreach_post("/api/public/li_account/GetAll", {"limit": 100, "offset": 0})
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
