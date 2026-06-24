import json
from http.server import BaseHTTPRequestHandler


def json_handler(data):
    body = json.dumps(data).encode()
    return (
        200,
        {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        body,
    )


def error_handler(msg, status=500):
    body = json.dumps({"error": msg}).encode()
    return (status, {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}, body)


def write_response(self, status, headers, body):
    self.send_response(status)
    for k, v in headers.items():
        self.send_header(k, v)
    self.end_headers()
    self.wfile.write(body)
