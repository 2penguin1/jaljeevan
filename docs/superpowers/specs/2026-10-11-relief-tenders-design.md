# Relief tenders: lean CRM for the demo (design + plan)

Approved in chat on 2026-10-11 at about 20:50 IST (deadline tonight). It uses the existing tables in `models/crm.py`. Code does every number; there is no AI in this flow.

## Rules (domain, pure)

- **Relief need** (`domain/relief.py`):
  - `rural people in the dry parts × 20 L/person/day × tanker share`;
  - the default share is 0.10, editable in the form;
  - the need is reported in kL/day and as 10 kL tanker trips per day;
  - population falls back to the whole zone when the urban split is unknown.
- **Matching** (`domain/matching.py`):
  - **eligibility:** `haversine × 1.3 ≤ radius` and `tanker_count > 0`;
  - **score:** `0.35·(1 − d/r) + 0.25·(cheapest/price) + 0.2·min(1, capacity per day ÷ need) + 0.2·reliability`;
  - the top 6 are invited, each with a plain reason;
  - **suggested price:** the median `base_price_per_kl` of the eligible vendors, else ₹60.
- **Bid state machine** (`domain/bids.py`), a dict of allowed transitions:

  | From | Allowed next states |
  |---|---|
  | `invited` | accepted, countered, declined |
  | `countered` | accepted, countered, declined |
  | `accepted` | (none) |
  | `declined` | (none) |

  - `turn` flips on each counter.
  - Only the side whose turn it is may act. An illegal action → 409.
  - "Accept" agrees the latest offer.
- **Committed:** the sum of `qty_per_day` over agreed offers, divided by the tender's `qty_per_day`.

## API (`/api/v1`)

Reads are public; writes need `X-Admin-Token` (the demo access code).

| Method and path | What it does |
|---|---|
| `GET /zones/{id}/relief-need?share=0.1` | the need with its formula |
| `POST /tenders` | `{zone_id, qty_per_day, duration_days, price_per_unit, radius_km}` → publishes and invites |
| `GET /tenders` | the list |
| `GET /tenders/{id}` | the tender, its bids (vendor, distance, reason, status, turn, latest offer), messages and committed figure |
| `POST /tenders/{id}/bids/{bid_id}/actions` | `{side: gov\|vendor, action: accept\|counter\|decline, price_per_unit?, qty_per_day?, note?}` |
| `GET /vendors` | the demo vendors, for the "viewing as" picker |

## Seed

`app/cli/seed_crm.py` (idempotent) creates:
- 1 government organisation: Relief & Rehabilitation, Maharashtra;
- a demo officer user;
- 16 demo tanker vendors near the drought talukas of Maharashtra and Karnataka (`is_demo=true`).

## UI

- **Zone page:** a "Relief need" card with the formula, plus a "Create tanker tender" form (prefilled, demo code asked once and kept in sessionStorage).
- **`/tenders` list:** a sidebar item.
- **`/tenders/:id`:**
  - the summary and the committed bar;
  - the vendor table with reasons;
  - a "Viewing as: Government / vendor ▾" switch;
  - action buttons for whoever has the turn;
  - the message log.

## Tasks

1. **Domain:** relief, matching and bids, with tests.
2. **Service, repository and API**, with tests (the PostGIS test DB).
3. **Seed CLI.**
4. **Frontend:** types, `apiPost`, hooks, zone card + form, tenders pages; Vitest.
5. **Deploy:**
   - build;
   - `cdk deploy`;
   - run the seed as an ECS task;
   - a live run-through;
   - a new video-script scene.
