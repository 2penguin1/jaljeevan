# Accounts, login and real negotiation (design + plan)

Approved in chat on 2026-10-11 (about 21:50 IST). This is pieces 1 and 2 of the full CRM. It replaces the "Viewing as" switch and the shared demo code on tenders. Built on branch `feat/accounts`; it is deployed only when everything is green.

## Security

- **`core/security.py`:**
  - bcrypt hash and verify;
  - JWT HS256 with claims `sub` (user id), `role`, `org`, `exp` (12 h);
  - the key is `JWT_SECRET`. The app refuses to issue tokens without it, except in tests and local development, which use a fixed development key.
- **Cookie:** `session`, set as `httpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` when `COOKIE_SECURE=true` (on AWS). Writes also require a JSON body, so plain HTML forms from other sites cannot post.
- **Dependencies (`api/dependencies.py`):**
  - `current_user`: 401 when the cookie is missing, invalid or expired;
  - `require_role(*roles)`: 403 when the role is wrong.
- **Login brake:** at most 5 failed attempts per email per minute (in memory, per process) → 429.
- **Signup:** creates a `citizen` with no organisation. Any `role` or `org_id` in the body is ignored, because the schema doesn't accept them.
- **Seeds (`cli/seed_crm.py`):**
  - officer `officer@relief.demo` (gov_admin, government organisation);
  - vendors `akkalkot@vendor.demo`, `solapur@vendor.demo`, `latur@vendor.demo` (role vendor, linked to their organisation);
  - NGO `ngo@relief.demo` (role ngo, plus an NGO organisation);
  - password = `DEMO_PASSWORD`; seeding is skipped with a message when it isn't set.

## Negotiation rules

The side comes from the user: `gov_admin` → gov, `vendor` → vendor (only on bids of its own organisation, otherwise 403).

- **`accept` / `counter` / `decline`:** as before (`domain/bids.py`).
- **`message`:** allowed on any open or finished bid, for both sides. It adds a human `BidMessage` (side, author) and changes neither status nor turn.
- **Raise price** (`POST /tenders/{id}/raise-price {price_per_unit}`, gov only, higher than the current tender price):
  - every open bid (invited or countered) gets a new gov offer (v+1, same quantity, new price) and the previous one is superseded;
  - turn → vendor, status `countered` (or stays `invited`);
  - a system message is posted;
  - `tender.price_per_unit` is updated.
- **Version check:** `expected_version` is required on every bid action. If it doesn't match `bid.version` → 409 "This bid changed. Reload to see the latest offer." Messages don't need it.
- **Inbox** (`GET /inbox`, vendor): the bids of my organisation, as `needs_action` (open, turn vendor), `waiting` (open, turn gov) and `closed` (accepted or declined). Each bid carries the tender, zone and latest offer.
- **Tender list for gov:** adds `waiting_for_gov` (open bids with turn gov) to each summary.

## API changes

- **New:** `/api/v1/auth/login|logout|me|signup`, `GET /api/v1/inbox`, `POST /api/v1/tenders/{id}/raise-price`.
- **Tender writes** now need a session instead of `X-Admin-Token`: create and raise-price for gov_admin; bid actions for gov_admin or vendor.
- **`BidActionIn`** loses `side`, gains `expected_version`, and the actions now include `message`, with `body` required.
- **Reads** stay public.

## Frontend

- **Session:** `useMe()` (`GET /auth/me`, 401 → logged out). The top bar shows the user's name and role plus Log out, or "Log in".
- **Pages:**
  - `/login` (email, password);
  - `/signup` (citizen);
  - `/inbox` (vendor; a sidebar item when the user is a vendor).
- **Tender page:**
  - the actions shown depend on the logged-in user;
  - the message box appears for the parties;
  - "Raise price" appears for the officer;
  - a 409 shows "This bid changed" and refetches.
- **Zone page:** "Create tanker tender" only for gov_admin; others see "Log in as a relief officer to create a tender".
- **Removed:** the "Viewing as" switch, the demo code field and `demoCode.ts`.

## Deploy

- Add `JWT_SECRET` (generated) and `DEMO_PASSWORD` (generated) to the `jal/app` secret through `put_app_secret.py`; both are saved to `backend/.env`.
- The stack maps them, plus `COOKIE_SECURE=true`.
- Re-run the seed task, then a live check.

## Tasks

1. **Security core:** hashing, tokens, cookie helpers, dependencies, login brake (tests).
2. **Auth API and seeds** (tests).
3. **Negotiation:** side from the user, message, raise price, version check, inbox, `waiting_for_gov` (tests).
4. **Frontend:** session, login and signup, inbox, tender page by role, zone gating (Vitest).
5. **Deploy:** secrets, stack env, seed, live run-through; docs (CLAUDE.md, DECISIONS, REMINDERS, video script).
