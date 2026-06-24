import json
from http.server import BaseHTTPRequestHandler
from lib.client import heyreach_post
from lib.util import json_handler, error_handler, write_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            campaigns = heyreach_post("/api/public/campaign/GetAll", {"limit": 100, "offset": 0})
            lists = heyreach_post("/api/public/list/GetAll", {"limit": 100, "offset": 0})
            accounts = heyreach_post("/api/public/li_account/GetAll", {"limit": 100, "offset": 0})
            inbox = heyreach_post(
                "/api/public/inbox/GetConversationsV2", {"limit": 1, "offset": 0}
            )

            camp_items = campaigns.get("items", [])
            list_items = lists.get("items", [])
            total_leads = sum(l.get("totalItemsCount", 0) for l in list_items)

            statuses = {}
            for c in camp_items:
                s = c.get("status", "UNKNOWN")
                statuses[s] = statuses.get(s, 0) + 1

            data = {
                "totalCampaigns": len(camp_items),
                "activeCampaigns": statuses.get("IN_PROGRESS", 0),
                "totalLists": len(list_items),
                "totalAccounts": len(accounts.get("items", [])),
                "totalLeads": total_leads,
                "totalInbox": inbox.get("totalCount", 0) if isinstance(inbox, dict) else 0,
                "statusBreakdown": statuses,
                "inboxError": "error" in inbox if isinstance(inbox, dict) else True,
            }
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
