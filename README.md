# BP-reach Dashboard

A view-only dashboard for HeyReach (LinkedIn outreach). Nothing in it can create, edit, start, pause or delete anything in HeyReach.

- **Users** sign in with an email and password and see **one LinkedIn account only**: its campaigns, lead lists, inbox, network and stats. This is enforced on the server (`api/proxy.py`), not just hidden in the page.
- **The admin** signs in at `/admin`, sees every LinkedIn account connected in HeyReach, and creates, changes, disables or removes logins. The admin can also open the dashboard and switch between all accounts.

## Setup on Vercel

1. **Environment variables** (Project → Settings → Environment Variables)

   | Name | Required | What it is |
   |---|---|---|
   | `HEYREACH_API_KEY` | yes | Your HeyReach API key |
   | `ADMIN_PASSWORD` | yes | Password for the admin login. Use a long, unique one |
   | `ADMIN_EMAIL` | no | Admin login name. Defaults to `admin` |
   | `SESSION_SECRET` | recommended | Any long random string. Signs the login cookies |

2. **Storage for logins.** Vercel functions have no disk, so logins are kept in Redis.
   In Vercel: Storage → Create → **Upstash for Redis** (free tier is enough) → connect it to this project.
   That adds `KV_REST_API_URL` and `KV_REST_API_TOKEN` automatically.

3. **Redeploy**, open `/admin`, sign in, and click **Create login** next to each LinkedIn account.
   Send the person their login email and password. They sign in at the site root.

Until step 2 is done the admin panel shows a "Logins can't be saved yet" message and only the admin can sign in.

## How logins work

- Passwords are stored as salted PBKDF2-SHA256 hashes. They can't be read back, only replaced.
- Changing a password, disabling or removing a login signs that person out immediately.
- 8 wrong passwords for the same email blocks further attempts for 15 minutes.
- Sessions last 12 hours, in an HttpOnly, Secure, SameSite=Strict cookie.
- Changing `SESSION_SECRET` (or `ADMIN_PASSWORD` if no secret is set) signs everyone out.

## What a user can and cannot see

A campaign belongs to a user if their LinkedIn account is one of its senders. A list belongs to them if one of those campaigns uses it.
If two LinkedIn accounts share a campaign, both users see that campaign and its leads; stats and inbox are still per account.
Webhooks and the account switcher are admin-only.

## Stats

All numbers on the Overview and Analytics pages cover the date range chosen at the top (default: last 30 days, UTC).
Totals come from HeyReach `GetOverallStats`, the per-campaign table from `GetOverallStatsByCampaign`, both with the same range and account.
Acceptance rate = accepted / connections sent. Reply rate = replies / conversations started (falls back to messages sent). Rates are always calculated from totals, never averaged per day.

## Files

- `api/proxy.py`: the API (auth, account scoping, HeyReach calls, stats)
- `public/index.html`: dashboard and sign-in
- `public/admin.html`: admin panel, served at `/admin`
