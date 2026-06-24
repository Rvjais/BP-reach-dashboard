import json
import os
import urllib.error
import urllib.request

API_BASE = "https://api.heyreach.io"


def heyreach_post(path, body):
    api_key = os.environ.get("HEYREACH_API_KEY", "")
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "heyreach-dashboard/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"API error: {e.code} {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}
