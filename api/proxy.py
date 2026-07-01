import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler

API_BASE = "https://api.heyreach.io"


def heyreach_api(api_path, body=None, method="POST"):
    api_key = os.environ.get("HEYREACH_API_KEY", "")
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{api_path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"API error: {e.code} {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}


def write_json(self, data):
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    body = json.dumps(data).encode()
    try:
        self.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass


def read_body(self):
    try:
        cl = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(cl).decode()) if cl else {}
    except Exception:
        return {}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        result = self._route(path, params, None, "GET")
        if result is not None:
            write_json(self, result)
            return
        write_json(self, {"error": "Not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        body = read_body(self)

        result = self._route(path, params, body, "POST")
        if result is not None:
            write_json(self, result)
            return
        write_json(self, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-KEY")
        self.end_headers()

    def _route(self, path, params, body, method):
        if path == "/api/campaigns":
            return heyreach_api("/api/public/campaign/GetAll", {"limit": int(params.get("limit", [100])[0]), "offset": 0})

        if path == "/api/campaigns/getById":
            cid = (body or {}).get("campaignId") or (body or {}).get("id") or params.get("campaignId", [None])[0]
            if not cid:
                return {"error": "campaignId required"}
            return heyreach_api(f"/api/public/campaign/GetById?campaignId={cid}", method="GET")

        if path == "/api/campaigns/leads":
            return heyreach_api("/api/public/campaign/GetLeadsFromCampaign", body or params)

        if path == "/api/campaigns/sequence":
            cid = params.get("campaignId", [None])[0]
            if not cid:
                return {"error": "campaignId required"}
            return heyreach_api(f"/api/public/campaign/GetCampaignSequence?campaignId={cid}", method="GET")

        if path == "/api/campaigns/forLead":
            return heyreach_api("/api/public/campaign/GetCampaignsForLead", body)

        if path == "/api/campaigns/stopLead":
            return heyreach_api("/api/public/campaign/StopLeadInCampaign", body)

        if path == "/api/campaigns/addLeads":
            return heyreach_api("/api/public/campaign/AddLeadsToCampaign", body)

        if path == "/api/campaigns/addLeadsV2":
            return heyreach_api("/api/public/campaign/AddLeadsToCampaignV2", body)

        if path in ("/api/campaigns/create", "/api/campaigns/updateSettings", "/api/campaigns/updateSchedule", "/api/campaigns/updateAccounts", "/api/campaigns/updateSequence"):
            sub = path.split("/")[-1]
            mapping = {"create": "create", "updateSettings": "update-settings", "updateSchedule": "update-schedule", "updateAccounts": "update-accounts", "updateSequence": "update-sequence"}
            # These need CLI, return error for Vercel
            return {"error": f"Campaign {mapping.get(sub, sub)} requires CLI, use dev server"}

        if path in ("/api/campaigns/pause", "/api/campaigns/resume", "/api/campaigns/start"):
            return {"error": f"Campaign {path.split('/')[-1]} requires CLI, use dev server"}

        if path == "/api/campaigns/delete":
            cid = (body or {}).get("campaignId") or params.get("campaignId", [None])[0]
            if not cid:
                return {"error": "campaignId required"}
            return heyreach_api(f"/api/public/campaign/DeleteCampaign?campaignId={cid}", method="DELETE")

        if path == "/api/campaigns/createFromTemplate":
            return heyreach_api("/api/public/campaign/CreateCampaignFromTemplate", body)

        # Lists
        if path == "/api/lists":
            return heyreach_api("/api/public/list/GetAll", {"limit": int(params.get("limit", [100])[0]), "offset": 0})

        if path == "/api/lists/getById":
            lid = params.get("listId", [None])[0]
            if not lid:
                return {"error": "listId required"}
            return heyreach_api(f"/api/public/list/GetById?listId={lid}", method="POST")

        if path == "/api/lists/leads":
            return heyreach_api("/api/public/list/GetLeadsFromList", body)

        if path == "/api/lists/addLeads":
            return heyreach_api("/api/public/list/AddLeadsToList", body)

        if path == "/api/lists/addLeadsV2":
            return heyreach_api("/api/public/list/AddLeadsToListV2", body)

        if path == "/api/lists/deleteLeads":
            return heyreach_api("/api/public/list/RemoveLeadsFromList", body)

        if path == "/api/lists/deleteLeadsByProfileUrl":
            return heyreach_api("/api/public/list/DeleteLeadsFromListByProfileUrl", body, method="DELETE")

        if path == "/api/lists/companies":
            return heyreach_api("/api/public/list/GetCompaniesFromList", body)

        if path == "/api/lists/forLead":
            return heyreach_api("/api/public/list/GetListsForLead", body)

        if path == "/api/lists/create":
            return heyreach_api("/api/public/list/CreateEmptyList", body)

        # Accounts
        if path == "/api/accounts":
            return heyreach_api("/api/public/li_account/GetAll", {"limit": 100, "offset": 0})

        if path == "/api/accounts/getById":
            aid = params.get("accountId", [None])[0]
            if not aid:
                return {"error": "accountId required"}
            return heyreach_api(f"/api/public/li_account/GetById?accountId={aid}", method="GET")

        if path == "/api/accounts/getAll":
            return heyreach_api("/api/public/li_account/GetAll", body or {})

        # Inbox
        if path == "/api/inbox":
            offset = int(params.get("offset", [0])[0])
            limit = int(params.get("limit", [20])[0])
            req_body = {"offset": offset, "limit": limit}
            aid = params.get("accountId", [None])[0]
            if aid:
                req_body["filters"] = {"linkedInAccountIds": [int(aid)]}
            return heyreach_api("/api/public/inbox/GetConversationsV2", req_body)

        if path == "/api/inbox/send":
            return heyreach_api("/api/public/inbox/SendMessage", body)

        if path == "/api/inbox/setSeen":
            return heyreach_api("/api/public/inbox/SetConversationSeen", body)

        if path == "/api/inbox/chatroom":
            aid = params.get("accountId", [None])[0]
            cid = params.get("conversationId", [None])[0]
            if not aid or not cid:
                return {"error": "accountId and conversationId required"}
            return heyreach_api(f"/api/public/inbox/GetChatroom/{aid}/{cid}", method="GET")

        # Stats
        if path in ("/api/stats", "/api/stats/by-campaign"):
            raw = heyreach_api("/api/public/stats/GetOverallStatsByCampaign", {"accountIds": [], "campaignIds": []})
            if "error" in raw:
                return raw
            if "byDayStats" in raw:
                by_campaign = {}
                for day_stats in raw["byDayStats"].values():
                    for entry in day_stats:
                        cid = entry.get("campaignId")
                        if cid not in by_campaign:
                            by_campaign[cid] = dict(entry)
                            by_campaign[cid]["days"] = 1
                        else:
                            for k, v in entry.items():
                                if isinstance(v, (int, float)) and k not in ("campaignId", "isCampaignDeleted"):
                                    by_campaign[cid][k] = by_campaign[cid].get(k, 0) + v
                            by_campaign[cid]["days"] += 1
                for cid in by_campaign:
                    days = max(by_campaign[cid]["days"], 1)
                    for k in list(by_campaign[cid].keys()):
                        if k.endswith("Rate"):
                            by_campaign[cid][k] = round(by_campaign[cid].get(k, 0) / days, 4)
                return {"items": list(by_campaign.values())}
            return raw

        if path == "/api/stats/getOverall":
            return heyreach_api("/api/public/stats/GetOverallStats", body)

        # Leads & Tags
        if path == "/api/lead/tags":
            return heyreach_api("/api/public/lead/GetLeadTags", body)

        if path == "/api/lead/addTags":
            return heyreach_api("/api/public/lead/AddTagsToLead", body)

        if path == "/api/lead/replaceTags":
            return heyreach_api("/api/public/lead/ReplaceTags", body)

        if path == "/api/lead/get":
            return heyreach_api("/api/public/lead/GetLeadFromProfile", body)

        if path == "/api/lead_tags/createTags":
            return heyreach_api("/api/public/lead_tags/CreateTags", body)

        # Network
        if path == "/api/network/get":
            return heyreach_api("/api/public/MyNetwork/GetMyNetworkForSender", {
                "pageNumber": body.get("offset", 0) // 100,
                "pageSize": body.get("limit", 100),
                "senderId": body.get("linkedInAccountId", 0)
            })

        if path == "/api/network/isConnection":
            return heyreach_api("/api/public/MyNetwork/IsConnection", {
                "senderAccountId": body.get("linkedInAccountId", 0),
                "leadProfileUrl": body.get("profileUrl", body.get("leadProfileUrl", ""))
            })

        # Overview
        if path == "/api/overview":
            campaigns = heyreach_api("/api/public/campaign/GetAll", {"limit": 100, "offset": 0})
            lists = heyreach_api("/api/public/list/GetAll", {"limit": 100, "offset": 0})
            accounts = heyreach_api("/api/public/li_account/GetAll", {"limit": 100, "offset": 0})
            inbox = heyreach_api("/api/public/inbox/GetConversationsV2", {"limit": 1, "offset": 0})
            camp_items = campaigns.get("items", [])
            list_items = lists.get("items", [])
            statuses = {}
            for c in camp_items:
                s = c.get("status", "UNKNOWN")
                statuses[s] = statuses.get(s, 0) + 1
            return {
                "totalCampaigns": len(camp_items),
                "activeCampaigns": statuses.get("IN_PROGRESS", 0),
                "totalLists": len(list_items),
                "totalLeads": sum(l.get("totalItemsCount", 0) for l in list_items),
                "totalAccounts": len(accounts.get("items", [])),
                "totalInbox": inbox.get("totalCount", 0) if isinstance(inbox, dict) else 0,
                "statusBreakdown": statuses,
                "inboxError": "error" in inbox if isinstance(inbox, dict) else True,
            }

        # Webhooks
        if path == "/api/webhooks":
            return heyreach_api("/api/public/webhooks/GetAllWebhooks", {"limit": 100, "offset": 0})

        if path == "/api/webhooks/getById":
            wid = params.get("webhookId", [None])[0]
            if not wid:
                return {"error": "webhookId required"}
            return heyreach_api(f"/api/public/webhooks/GetWebhookById?webhookId={wid}&includeCustomHeaders=false", method="GET")

        if path == "/api/webhooks/create":
            return heyreach_api("/api/public/webhooks/CreateWebhook", body)

        if path == "/api/webhooks/delete":
            wid = (body or {}).get("webhookId") or (body or {}).get("id") or params.get("webhookId", [None])[0]
            if not wid:
                return {"error": "webhookId required"}
            return heyreach_api(f"/api/public/webhooks/DeleteWebhook?webhookId={wid}", method="DELETE")

        if path == "/api/webhooks/update":
            return heyreach_api(f"/api/public/webhooks/UpdateWebhook?webhookId={(body or {}).get('id')}", body)

        # Auth
        if path == "/api/auth/check":
            return heyreach_api("/api/public/auth/CheckApiKey", method="GET")

        # Team / Org (require master key in env)
        if "team" in path:
            master_key = os.environ.get("HEYREACH_API_KEY", "")
            if not master_key:
                return {"error": "No master API key configured"}

            if path == "/api/team/workspaces":
                return heyreach_api("/api/public/management/organizations/workspaces?Offset=0&Limit=100", method="GET")

            if path == "/api/team/workspace-keys":
                wsid = params.get("workspaceId", [None])[0]
                if not wsid:
                    return {"error": "workspaceId required"}
                return heyreach_api(f"/api/public/management/organizations/api-keys/workspaces/{wsid}", method="GET")

            if path == "/api/team/workspace-keys-create":
                wsid = (body or {}).get("workspaceId")
                if not wsid:
                    return {"error": "workspaceId required"}
                return heyreach_api(f"/api/public/management/organizations/api-keys/workspaces/{wsid}", body)

            if path == "/api/team/workspace-create":
                return heyreach_api("/api/public/management/organizations/workspaces", body)

            if path == "/api/team/workspace-update":
                wsid = (body or {}).get("workspaceId")
                if not wsid:
                    return {"error": "workspaceId required"}
                return heyreach_api(f"/api/public/management/organizations/workspaces/{wsid}", body, method="PATCH")

            if path == "/api/team/all-users":
                return heyreach_api("/api/public/management/organizations/users", body)

            if path == "/api/team/invite-admins":
                return heyreach_api("/api/public/management/organizations/users/invite/admins", body)

            if path == "/api/team/invite-members":
                return heyreach_api("/api/public/management/organizations/users/invite/members", body)

            if path == "/api/team/invite":
                return heyreach_api("/api/public/management/organizations/users/invite/managers", body)

            if path == "/api/team/user":
                uid = params.get("userId", [None])[0]
                if not uid:
                    return {"error": "userId required"}
                return heyreach_api(f"/api/public/management/organizations/users/{uid}", method="GET")

            if path.startswith("/api/team/users"):
                wsid = params.get("workspaceId", [None])[0] or (body or {}).get("workspaceId")
                if wsid:
                    return heyreach_api(f"/api/public/management/organizations/users/workspaces/{wsid}", body)
                return heyreach_api("/api/public/management/organizations/users", body)

        # Settings
        if path == "/api/settings/keys":
            return {"error": "Cannot save keys on Vercel, set HEYREACH_API_KEY env variable"}

        return None
