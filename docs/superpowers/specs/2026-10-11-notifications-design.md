# In-app notifications (design + plan)

Piece 3 of the full CRM, decided by me on 2026-10-11 under the user's standing instruction to decide and build end to end.

## Rules

- **`NotificationService.notify(user_ids, kind, payload)`** inserts one row per user into the existing `notifications` table.
  - `payload = {tender_id, text, link}`.
  - `text` is the same sentence as the bid thread's system message, so the two never disagree.
- **Triggers** (inside `TenderService`, same transaction):

  | Event | Kind | Who is notified |
  |---|---|---|
  | `create` | `tender_invite` | the users of every invited vendor organisation: "New tender: X kL a day near <zone> at ₹Y/kL" |
  | vendor action (counter / accept / decline / message) | `bid_update` | the users of the tender's government organisation |
  | gov action (counter / accept / decline / message) | `bid_update` | the users of that bid's vendor organisation |
  | `raise_price` | `bid_update` | the users of every open bid's vendor organisation |

- **The actor is never notified about their own action.**
- **Privacy:** notifications are private to their user. No live broadcast: the SSE feed is shared by every visitor.

## API

Logged in; each user sees only their own.

- `GET /api/v1/notifications` → `{unread, items: [{id, kind, text, link, created_at, read}]}`, the latest 30.
- `POST /api/v1/notifications/read` with `{ids?: [...]}`; no ids means "all mine". Ids belonging to another user are ignored.

## Frontend

A bell in the top bar for logged-in users:
- an unread badge;
- a panel listing items that link to the tender, with "Mark all read";
- polling every 15 s, and refreshing after any bid action.

## Not in this piece

Email through SNS (needs real, confirmed addresses), SMS, and live push.

## Tasks

1. **Repository and service:** `NotificationRepository` (`org_user_ids`, `add_many`, `latest`, `unread_count`, `mark_read`) and `NotificationService` (tests).
2. **Triggers in `TenderService`** (tests: who gets what, never the actor).
3. **API** (tests: 401, only your own, mark read).
4. **Frontend bell** (Vitest), then deploy.
