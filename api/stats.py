from http.server import BaseHTTPRequestHandler
from shared import heyreach_post, json_handler, error_handler, write_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            raw = heyreach_post(
                "/api/public/stats/GetOverallStatsByCampaign",
                {"accountIds": [], "campaignIds": []},
            )
            if "error" in raw:
                status, headers, body = json_handler(raw)
            elif "byDayStats" in raw:
                by_campaign = {}
                for day_stats in raw["byDayStats"].values():
                    for entry in day_stats:
                        cid = entry.get("campaignId")
                        if cid not in by_campaign:
                            by_campaign[cid] = dict(entry)
                            by_campaign[cid]["days"] = 1
                        else:
                            for k, v in entry.items():
                                if isinstance(v, (int, float)) and k not in (
                                    "campaignId",
                                    "isCampaignDeleted",
                                ):
                                    by_campaign[cid][k] = by_campaign[cid].get(k, 0) + v
                            by_campaign[cid]["days"] += 1
                for cid in by_campaign:
                    days = max(by_campaign[cid]["days"], 1)
                    for k in list(by_campaign[cid].keys()):
                        if k.endswith("Rate"):
                            by_campaign[cid][k] = round(by_campaign[cid].get(k, 0) / days, 4)
                data = {"items": list(by_campaign.values())}
                status, headers, body = json_handler(data)
            else:
                status, headers, body = json_handler(raw)
        except Exception as e:
            status, headers, body = error_handler(str(e))
        write_response(self, status, headers, body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
