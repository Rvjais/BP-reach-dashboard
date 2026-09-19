"""BP-reach dashboard API.

Read-only proxy in front of the HeyReach public API, with login:
  - users sign in with email + password and are locked (server-side) to ONE LinkedIn account
  - the admin manages those logins at /admin and can view every account

Environment variables:
  HEYREACH_API_KEY   HeyReach API key (required)
  ADMIN_PASSWORD     password for the admin login (required to use /admin)
  ADMIN_EMAIL        admin login name (default: "admin")
  SESSION_SECRET     optional; random string used to sign session cookies
  KV_REST_API_URL / KV_REST_API_TOKEN   Upstash Redis REST credentials (login storage on Vercel)
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

API_BASE = "https://api.heyreach.io"

SESSION_COOKIE = "bp_session"
SESSION_TTL = 12 * 3600
PBKDF2_ITERATIONS = 210_000
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_FAILURES = 8
LOGIN_FAILURE_WINDOW = 15 * 60

USERS_KEY = "bp:users"

# Everything a signed-in user may call. Anything else is admin-only.
USER_PATHS = {
    "/api/overview", "/api/stats",
    "/api/campaigns", "/api/campaigns/getById", "/api/campaigns/leads", "/api/campaigns/sequence",
    "/api/lists", "/api/lists/leads", "/api/lists/companies",
    "/api/accounts", "/api/accounts/getById",
    "/api/inbox", "/api/inbox/chatroom",
    "/api/network/get", "/api/network/isConnection",
}


# ───────────────────────── HeyReach client ─────────────────────────

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
            raw = resp.read().decode().strip()
            # Some endpoints (e.g. GetCampaignSequence with no sequence) return an empty 200
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except ValueError:
                return {"result": raw}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            raw = e.read().decode().strip()
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        detail = parsed.get("errorMessage") or parsed.get("message") or parsed.get("detail") or parsed.get("title") or raw
                    else:
                        detail = str(parsed)
                except ValueError:
                    detail = raw
        except Exception:
            pass
        msg = f"API error: {e.code} {e.reason}"
        if detail:
            msg += f" - {str(detail)[:500]}"
        return {"error": msg}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}


def fetch_all(api_path, extra=None, page_size=100, max_pages=30):
    """Page through a HeyReach GetAll-style endpoint so counts aren't capped at one page."""
    items, offset, total = [], 0, None
    for _ in range(max_pages):
        body = dict(extra or {})
        body.update({"offset": offset, "limit": page_size})
        res = heyreach_api(api_path, body)
        if not isinstance(res, dict) or "error" in res:
            if not items:
                return res if isinstance(res, dict) else {"error": "Unexpected response"}
            return {"items": items, "totalCount": total or len(items), "partial": True}
        batch = res.get("items") or []
        items.extend(batch)
        total = res.get("totalCount", total)
        offset += len(batch)
        if len(batch) < page_size or (total is not None and len(items) >= total):
            break
    return {"items": items, "totalCount": total if total is not None else len(items)}


def parallel(**calls):
    """Run independent HeyReach calls concurrently (the function has a 30s budget)."""
    with ThreadPoolExecutor(max_workers=max(len(calls), 1)) as pool:
        futures = {name: pool.submit(fn) for name, fn in calls.items()}
        return {name: f.result() for name, f in futures.items()}


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ───────────────────────── Account scoping ─────────────────────────

def campaigns_for(aid=None):
    """All campaigns, or only those a LinkedIn account sends from."""
    res = fetch_all("/api/public/campaign/GetAll", {"accountIds": [aid]} if aid else {})
    if "error" in res or not aid:
        return res
    # Don't rely on the API filter alone
    res["items"] = [c for c in res["items"]
                    if not isinstance(c.get("campaignAccountIds"), list) or aid in c["campaignAccountIds"]]
    res["totalCount"] = len(res["items"])
    return res


def lists_for(aid=None, campaigns=None):
    """All lists, or only those used by the account's campaigns."""
    res = fetch_all("/api/public/list/GetAll")
    if "error" in res or not aid:
        return res
    campaigns = campaigns if campaigns is not None else campaigns_for(aid)
    if "error" in campaigns:
        return campaigns
    camp_ids = {c.get("id") for c in campaigns["items"]}
    list_ids = {c.get("linkedInUserListId") for c in campaigns["items"]}
    res["items"] = [l for l in res["items"]
                    if l.get("id") in list_ids or camp_ids.intersection(l.get("campaignIds") or [])]
    res["totalCount"] = len(res["items"])
    return res


def owns_campaign(aid, campaign_id):
    camps = campaigns_for(aid)
    return "error" not in camps and any(c.get("id") == campaign_id for c in camps["items"])


def owns_list(aid, list_id):
    lists = lists_for(aid)
    return "error" not in lists and any(l.get("id") == list_id for l in lists["items"])


# ───────────────────────── Stats ─────────────────────────

def sum_stats(rows):
    """Sum the count fields of stat rows. Rates are never summed or averaged."""
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if k in ("campaignId", "isCampaignDeleted") or k.lower().endswith("rate"):
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = out.get(k, 0) + v
    return out


def with_rates(s):
    """Derive rates from totals so cards, table and chart always agree."""
    s = dict(s)
    sent = _num(s.get("connectionsSent"))
    started = _num(s.get("totalMessageStarted")) or _num(s.get("messagesSent"))
    in_started = _num(s.get("totalInmailStarted")) or _num(s.get("inmailMessagesSent"))
    # Same metrics HeyReach's own Performance page shows: leads messaged, not raw message count
    s["messagedLeads"] = started
    s["inmailedLeads"] = in_started
    s["acceptRate"] = round(_num(s.get("connectionsAccepted")) / sent, 4) if sent else None
    s["replyRate"] = round(_num(s.get("totalMessageReplies")) / started, 4) if started else None
    s["inmailReplyRate"] = round(_num(s.get("totalInmailReplies")) / in_started, 4) if in_started else None
    return s


def build_stats(params, aid):
    today = datetime.now(timezone.utc).date()
    date_to = params.get("to", [None])[0] or today.isoformat()
    date_from = params.get("from", [None])[0] or (today - timedelta(days=29)).isoformat()
    try:
        datetime.strptime(date_from, "%Y-%m-%d")
        datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        return {"error": "Dates must be YYYY-MM-DD"}
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    body = {
        "accountIds": [aid] if aid else [],
        "campaignIds": [],
        "startDate": f"{date_from}T00:00:00.000Z",
        "endDate": f"{date_to}T23:59:59.999Z",
    }
    res = parallel(
        overall=lambda: heyreach_api("/api/public/stats/GetOverallStats", body),
        by_campaign=lambda: heyreach_api("/api/public/stats/GetOverallStatsByCampaign", body),
    )
    overall, by_campaign = res["overall"], res["by_campaign"]
    if not isinstance(overall, dict):
        return {"error": "Unexpected stats response"}
    if "error" in overall:
        return overall

    # Daily series (one aggregated object per day)
    daily = []
    by_day = overall.get("byDayStats") or {}
    if isinstance(by_day, dict):
        for day in sorted(by_day.keys()):
            row = by_day[day]
            entry = with_rates(sum_stats(row if isinstance(row, list) else [row]))
            entry["date"] = str(day)[:10]
            daily.append(entry)

    totals = overall.get("overallStats")
    derived = ("messagedLeads", "inmailedLeads")
    totals = sum_stats([totals]) if isinstance(totals, dict) else sum_stats(
        [{k: v for k, v in d.items() if k not in derived} for d in daily])

    # Per-campaign: use the API's own per-campaign totals; only fall back to summing days
    campaigns, warning = [], None
    if isinstance(by_campaign, dict) and "error" not in by_campaign:
        per = by_campaign.get("overallStats")
        if isinstance(per, dict):
            per = list(per.values())
        if isinstance(per, list) and per:
            for row in per:
                if isinstance(row, dict):
                    c = sum_stats([row])
                    c.update({k: row.get(k) for k in ("campaignId", "campaignName", "isCampaignDeleted")})
                    campaigns.append(with_rates(c))
        else:
            grouped = {}
            days = by_campaign.get("byDayStats") or {}
            for day_rows in (days.values() if isinstance(days, dict) else []):
                for row in (day_rows if isinstance(day_rows, list) else [day_rows]):
                    if isinstance(row, dict):
                        grouped.setdefault(row.get("campaignId"), []).append(row)
            for cid, rows in grouped.items():
                c = sum_stats(rows)
                c.update({"campaignId": cid, "campaignName": rows[0].get("campaignName"),
                          "isCampaignDeleted": rows[0].get("isCampaignDeleted")})
                campaigns.append(with_rates(c))
    elif isinstance(by_campaign, dict):
        warning = "Per-campaign breakdown unavailable: " + str(by_campaign.get("error"))

    # Hide campaigns with no activity in the period
    campaigns = [c for c in campaigns if any(_num(v) for k, v in c.items() if k != "campaignId")]
    campaigns.sort(key=lambda c: _num(c.get("connectionsSent")) + _num(c.get("messagedLeads")), reverse=True)
    return {
        "range": {"from": date_from, "to": date_to},
        "accountId": aid,
        "totals": with_rates(totals),
        "daily": daily,
        "campaigns": campaigns,
        "warning": warning,
    }


def build_overview(aid):
    inbox_body = {"limit": 1, "offset": 0}
    if aid:
        inbox_body["filters"] = {"linkedInAccountIds": [aid]}
    res = parallel(
        campaigns=lambda: campaigns_for(aid),
        accounts=lambda: fetch_all("/api/public/li_account/GetAll"),
        inbox=lambda: heyreach_api("/api/public/inbox/GetConversationsV2", inbox_body),
    )
    campaigns, accounts, inbox = res["campaigns"], res["accounts"], res["inbox"]
    if "error" in campaigns:
        return campaigns
    lists = lists_for(aid, campaigns)
    camp_items = campaigns.get("items", [])
    list_items = lists.get("items", []) if "error" not in lists else []
    statuses = {}
    for c in camp_items:
        s = c.get("status") or "UNKNOWN"
        statuses[s] = statuses.get(s, 0) + 1
    lead_lists = [l for l in list_items if l.get("listType") != "COMPANY_LIST"]
    acc_items = accounts.get("items", []) if "error" not in accounts else []
    if aid:
        acc_items = [a for a in acc_items if a.get("id") == aid]
    inbox_ok = isinstance(inbox, dict) and "error" not in inbox
    return {
        "totalCampaigns": len(camp_items),
        "activeCampaigns": statuses.get("IN_PROGRESS", 0),
        "statusBreakdown": statuses,
        "totalLists": len(list_items),
        "leadLists": len(lead_lists),
        "companyLists": len(list_items) - len(lead_lists),
        "totalLeads": sum(_num(l.get("totalItemsCount")) for l in lead_lists),
        "totalAccounts": len(acc_items),
        "activeAccounts": sum(1 for a in acc_items if a.get("isActive")),
        "totalInbox": inbox.get("totalCount") if inbox_ok else None,
        "inboxError": None if inbox_ok else (inbox.get("error") if isinstance(inbox, dict) else "Unavailable"),
        "campaigns": camp_items,
        "partial": bool(campaigns.get("partial") or lists.get("partial")),
    }


# ───────────────────────── Login storage ─────────────────────────

class StoreError(Exception):
    pass


def _kv_config():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), token) if url and token else None


def _kv(*command):
    url, token = _kv_config()
    req = urllib.request.Request(
        url, data=json.dumps(list(command)).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()).get("result")
    except (urllib.error.URLError, ValueError) as e:
        raise StoreError(f"Login storage unavailable: {e}")


_LOCAL_FILE = Path(__file__).resolve().parent.parent / ".data" / "users.json"
_local_failures = {}


def storage_mode():
    if _kv_config():
        return "redis"
    # Vercel's filesystem is read-only and not shared between invocations
    return None if os.environ.get("VERCEL") else "file"


def _require_storage():
    mode = storage_mode()
    if not mode:
        raise StoreError("Login storage is not configured. Add the Upstash Redis integration in Vercel "
                         "(sets KV_REST_API_URL and KV_REST_API_TOKEN), then redeploy.")
    return mode


def _local_read():
    try:
        return json.loads(_LOCAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def users_all():
    if _require_storage() == "redis":
        raw = _kv("HGETALL", USERS_KEY) or []
        if isinstance(raw, dict):
            pairs = raw.items()
        else:
            pairs = zip(raw[0::2], raw[1::2])
        return {k: json.loads(v) for k, v in pairs}
    return _local_read()


def user_get(account_id):
    if _require_storage() == "redis":
        raw = _kv("HGET", USERS_KEY, str(account_id))
        return json.loads(raw) if raw else None
    return _local_read().get(str(account_id))


def user_put(record):
    key = str(record["accountId"])
    if _require_storage() == "redis":
        _kv("HSET", USERS_KEY, key, json.dumps(record))
        return
    data = _local_read()
    data[key] = record
    _LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def user_delete(account_id):
    if _require_storage() == "redis":
        _kv("HDEL", USERS_KEY, str(account_id))
        return
    data = _local_read()
    data.pop(str(account_id), None)
    _LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def login_blocked(email):
    key = "bp:fail:" + hashlib.sha256(email.encode()).hexdigest()[:32]
    if storage_mode() == "redis":
        return _int(_kv("GET", key) or 0) >= MAX_LOGIN_FAILURES
    count, since = _local_failures.get(key, (0, 0))
    return count >= MAX_LOGIN_FAILURES and time.time() - since < LOGIN_FAILURE_WINDOW


def login_failed(email):
    key = "bp:fail:" + hashlib.sha256(email.encode()).hexdigest()[:32]
    if storage_mode() == "redis":
        if _kv("INCR", key) == 1:
            _kv("EXPIRE", key, LOGIN_FAILURE_WINDOW)
        return
    count, since = _local_failures.get(key, (0, time.time()))
    if time.time() - since >= LOGIN_FAILURE_WINDOW:
        count, since = 0, time.time()
    _local_failures[key] = (count + 1, since)


def login_succeeded(email):
    key = "bp:fail:" + hashlib.sha256(email.encode()).hexdigest()[:32]
    if storage_mode() == "redis":
        _kv("DEL", key)
    else:
        _local_failures.pop(key, None)


# ───────────────────────── Passwords & sessions ─────────────────────────

def hash_password(password, salt=None, iterations=None):
    salt = salt or secrets.token_bytes(16)
    iterations = iterations or PBKDF2_ITERATIONS
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return salt.hex(), digest.hex(), iterations


def verify_password(password, record):
    try:
        _, digest, _ = hash_password(password, bytes.fromhex(record["salt"]), int(record.get("iter") or PBKDF2_ITERATIONS))
        return hmac.compare_digest(digest, record["hash"])
    except (KeyError, ValueError):
        return False


def _session_secret():
    explicit = os.environ.get("SESSION_SECRET")
    if explicit:
        return explicit.encode()
    base = os.environ.get("HEYREACH_API_KEY", "") + "|" + os.environ.get("ADMIN_PASSWORD", "")
    if base == "|":
        return None
    return hashlib.sha256(("bp-session|" + base).encode()).digest()


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_session(payload):
    secret = _session_secret()
    if not secret:
        return None
    payload = dict(payload, exp=int(time.time()) + SESSION_TTL)
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_session(cookie_header):
    """Return the verified session, or None. User sessions die when the login is changed/disabled."""
    secret = _session_secret()
    if not secret or not cookie_header:
        return None
    token = None
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == SESSION_COOKIE:
            token = value
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    expected = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        sess = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(sess, dict) or sess.get("exp", 0) < time.time():
        return None
    if sess.get("role") == "admin":
        return sess
    if sess.get("role") == "user":
        try:
            record = user_get(sess.get("accountId"))
        except StoreError:
            return None
        if record and record.get("enabled", True) and record.get("pv") == sess.get("pv"):
            return sess
    return None


def session_cookie(token, max_age=SESSION_TTL):
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={max_age}"


class Resp:
    def __init__(self, data, status=200, cookie=None):
        self.data, self.status, self.cookie = data, status, cookie


# ───────────────────────── Auth & admin routes ─────────────────────────

def do_login(body):
    email = str((body or {}).get("email") or "").strip().lower()
    password = str((body or {}).get("password") or "")
    if not email or not password:
        return Resp({"error": "Email and password are required"}, 400)
    if not _session_secret():
        return Resp({"error": "Server is not configured (HEYREACH_API_KEY / ADMIN_PASSWORD missing)"}, 500)
    try:
        if login_blocked(email):
            return Resp({"error": "Too many failed attempts. Try again in 15 minutes."}, 429)

        admin_email = (os.environ.get("ADMIN_EMAIL") or "admin").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD") or ""
        if admin_password and email == admin_email:
            if hmac.compare_digest(password.encode(), admin_password.encode()):
                login_succeeded(email)
                token = make_session({"role": "admin", "email": admin_email, "name": "Administrator"})
                return Resp({"role": "admin", "name": "Administrator", "email": admin_email}, cookie=session_cookie(token))
            login_failed(email)
            return Resp({"error": "Incorrect email or password"}, 401)

        record = None
        if storage_mode():
            record = next((u for u in users_all().values() if (u.get("email") or "").lower() == email), None)
        # Hash even when the user doesn't exist so timing doesn't reveal valid emails
        ok = verify_password(password, record) if record else (hash_password(password) and False)
        if not ok or not record.get("enabled", True):
            login_failed(email)
            return Resp({"error": "Incorrect email or password"}, 401)
        login_succeeded(email)
    except StoreError as e:
        return Resp({"error": str(e)}, 503)
    token = make_session({"role": "user", "accountId": record["accountId"], "pv": record.get("pv"),
                          "email": record["email"], "name": record.get("name") or record["email"]})
    return Resp({"role": "user", "accountId": record["accountId"], "name": record.get("name"), "email": record["email"]},
                cookie=session_cookie(token))


def admin_users():
    accounts = fetch_all("/api/public/li_account/GetAll")
    if "error" in accounts:
        return accounts
    storage, store_error, users = storage_mode(), None, {}
    try:
        users = users_all()
    except StoreError as e:
        store_error = str(e)
    rows, seen = [], set()
    for a in accounts["items"]:
        u = users.get(str(a.get("id"))) or {}
        seen.add(str(a.get("id")))
        rows.append({
            "accountId": a.get("id"),
            "name": f"{a.get('firstName') or ''} {a.get('lastName') or ''}".strip() or f"Account {a.get('id')}",
            "linkedinEmail": a.get("emailAddress"),
            "profileUrl": a.get("profileUrl"),
            "isActive": bool(a.get("isActive")),
            "activeCampaigns": a.get("activeCampaigns") or 0,
            "loginEmail": u.get("email"),
            "hasPassword": bool(u.get("hash")),
            "enabled": u.get("enabled", True) if u else False,
            "updatedAt": u.get("updatedAt"),
        })
    # Logins whose LinkedIn account no longer exists in HeyReach
    orphans = [{"accountId": u.get("accountId"), "name": u.get("name"), "loginEmail": u.get("email")}
               for k, u in users.items() if k not in seen]
    return {"items": rows, "orphans": orphans, "storage": storage, "storageError": store_error}


def admin_set_user(body):
    body = body or {}
    aid = _int(body.get("accountId"))
    email = str(body.get("email") or "").strip().lower()
    password = body.get("password")
    if not aid:
        return Resp({"error": "accountId required"}, 400)
    if not email or "@" not in email or len(email) > 200:
        return Resp({"error": "Enter a valid login email"}, 400)
    if email == (os.environ.get("ADMIN_EMAIL") or "admin").strip().lower():
        return Resp({"error": "That email is reserved for the admin login"}, 400)
    try:
        existing = user_get(aid)
        if any((u.get("email") or "").lower() == email and u.get("accountId") != aid for u in users_all().values()):
            return Resp({"error": "Another account already uses that login email"}, 400)
        if password is None and not existing:
            return Resp({"error": "Set a password to create this login"}, 400)
        account = heyreach_api(f"/api/public/li_account/GetById?accountId={aid}", method="GET")
        if not isinstance(account, dict) or "error" in account or not account.get("id"):
            return Resp({"error": "LinkedIn account not found in HeyReach"}, 400)

        record = dict(existing or {})
        record.update({
            "accountId": aid,
            "email": email,
            "name": f"{account.get('firstName') or ''} {account.get('lastName') or ''}".strip() or email,
            "enabled": bool(body.get("enabled", record.get("enabled", True))),
            "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if password is not None:
            password = str(password)
            if len(password) < MIN_PASSWORD_LENGTH:
                return Resp({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}, 400)
            record["salt"], record["hash"], record["iter"] = hash_password(password)
        # Any change signs the user out of existing sessions
        record["pv"] = secrets.token_hex(8)
        user_put(record)
    except StoreError as e:
        return Resp({"error": str(e)}, 503)
    return {"ok": True}


def admin_remove_user(body):
    aid = _int((body or {}).get("accountId"))
    if not aid:
        return Resp({"error": "accountId required"}, 400)
    try:
        user_delete(aid)
    except StoreError as e:
        return Resp({"error": str(e)}, 503)
    return {"ok": True}


# ───────────────────────── HTTP handler ─────────────────────────

def read_body(self):
    try:
        cl = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(cl).decode()) if 0 < cl <= 1_000_000 else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        body = read_body(self) if method == "POST" else None
        try:
            result = self._route(parsed.path.rstrip("/"), params, body, method)
        except StoreError as e:
            result = Resp({"error": str(e)}, 503)
        except Exception as e:  # never leak a stack trace to the browser
            result = Resp({"error": f"Server error: {type(e).__name__}"}, 500)
        if result is None:
            result = Resp({"error": "Not found"}, 404)
        if not isinstance(result, Resp):
            result = Resp(result)

        payload = json.dumps(result.data).encode()
        self.send_response(result.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if result.cookie:
            self.send_header("Set-Cookie", result.cookie)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _route(self, path, params, body, method):
        body = body or {}

        def param(name):
            return params.get(name, [None])[0] or body.get(name)

        # ── Auth ──
        if path == "/api/auth/login":
            return do_login(body) if method == "POST" else Resp({"error": "POST required"}, 405)

        if path == "/api/auth/logout":
            return Resp({"ok": True}, cookie=session_cookie("", 0))

        sess = read_session(self.headers.get("Cookie"))

        if path == "/api/auth/me":
            if not sess:
                return Resp({"error": "Not signed in"}, 401)
            return {k: sess.get(k) for k in ("role", "accountId", "name", "email")}

        if not sess:
            return Resp({"error": "Not signed in"}, 401)

        is_admin = sess.get("role") == "admin"
        if not is_admin and path not in USER_PATHS:
            return Resp({"error": "Not allowed"}, 403)

        # Users are pinned to their own LinkedIn account no matter what the browser sends
        aid = _int(param("accountId")) if is_admin else _int(sess.get("accountId"))
        if not is_admin and not aid:
            return Resp({"error": "Not allowed"}, 403)

        # ── Admin ──
        if path == "/api/admin/users":
            return admin_users()
        if path == "/api/admin/users/set":
            return admin_set_user(body) if method == "POST" else Resp({"error": "POST required"}, 405)
        if path == "/api/admin/users/remove":
            return admin_remove_user(body) if method == "POST" else Resp({"error": "POST required"}, 405)

        # ── Dashboard ──
        if path == "/api/overview":
            return build_overview(aid)

        if path == "/api/stats":
            return build_stats(params, aid)

        # ── Campaigns ──
        if path == "/api/campaigns":
            return campaigns_for(aid)

        if path in ("/api/campaigns/getById", "/api/campaigns/leads", "/api/campaigns/sequence"):
            cid = _int(param("campaignId"))
            if not cid:
                return Resp({"error": "campaignId required"}, 400)
            if not is_admin and not owns_campaign(aid, cid):
                return Resp({"error": "Campaign not found"}, 404)
            if path.endswith("getById"):
                return heyreach_api(f"/api/public/campaign/GetById?campaignId={cid}", method="GET")
            if path.endswith("sequence"):
                return heyreach_api(f"/api/public/campaign/GetCampaignSequence?campaignId={cid}", method="GET")
            return heyreach_api("/api/public/campaign/GetLeadsFromCampaign", {
                "campaignId": cid,
                "offset": max(_int(param("offset")) or 0, 0),
                "limit": min(max(_int(param("limit")) or 100, 1), 100),
            })

        # ── Lists ──
        if path == "/api/lists":
            return lists_for(aid)

        if path in ("/api/lists/leads", "/api/lists/companies"):
            lid = _int(param("listId"))
            if not lid:
                return Resp({"error": "listId required"}, 400)
            if not is_admin and not owns_list(aid, lid):
                return Resp({"error": "List not found"}, 404)
            endpoint = "GetLeadsFromList" if path.endswith("leads") else "GetCompaniesFromList"
            return heyreach_api(f"/api/public/list/{endpoint}", {
                "listId": lid,
                "offset": max(_int(param("offset")) or 0, 0),
                "limit": min(max(_int(param("limit")) or 100, 1), 100),
                "keyword": str(param("keyword") or "")[:100],
            })

        # ── LinkedIn accounts ──
        if path == "/api/accounts":
            res = fetch_all("/api/public/li_account/GetAll")
            if not is_admin and "error" not in res:
                res["items"] = [a for a in res["items"] if a.get("id") == aid]
                res["totalCount"] = len(res["items"])
            return res

        if path == "/api/accounts/getById":
            if not aid:
                return Resp({"error": "accountId required"}, 400)
            return heyreach_api(f"/api/public/li_account/GetById?accountId={aid}", method="GET")

        # ── Inbox ──
        if path == "/api/inbox":
            req_body = {
                "offset": max(_int(param("offset")) or 0, 0),
                "limit": min(max(_int(param("limit")) or 50, 1), 100),
            }
            if aid:
                req_body["filters"] = {"linkedInAccountIds": [aid]}
            return heyreach_api("/api/public/inbox/GetConversationsV2", req_body)

        if path == "/api/inbox/chatroom":
            conv = str(param("conversationId") or "")
            if not aid or not conv:
                return Resp({"error": "accountId and conversationId required"}, 400)
            return heyreach_api(f"/api/public/inbox/GetChatroom/{aid}/{urllib.parse.quote(conv, safe='')}", method="GET")

        # ── Network ──
        if path == "/api/network/get":
            if not aid:
                return Resp({"error": "accountId required"}, 400)
            return heyreach_api("/api/public/MyNetwork/GetMyNetworkForSender", {
                "pageNumber": max(_int(param("page")) or 0, 0),
                "pageSize": 100,
                "senderId": aid,
            })

        if path == "/api/network/isConnection":
            if not aid:
                return Resp({"error": "accountId required"}, 400)
            return heyreach_api("/api/public/MyNetwork/IsConnection", {
                "senderAccountId": aid,
                "leadProfileUrl": str(param("profileUrl") or "")[:500],
            })

        # ── Admin-only views (workspace-wide data) ──
        if path == "/api/webhooks":
            return fetch_all("/api/public/webhooks/GetAllWebhooks")

        if path == "/api/webhooks/getById":
            wid = _int(param("webhookId"))
            if not wid:
                return Resp({"error": "webhookId required"}, 400)
            return heyreach_api(f"/api/public/webhooks/GetWebhookById?webhookId={wid}&includeCustomHeaders=false", method="GET")

        if path == "/api/auth/check":
            return heyreach_api("/api/public/auth/CheckApiKey", method="GET")

        return None
