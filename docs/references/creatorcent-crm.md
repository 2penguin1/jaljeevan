# Reference: Creatorcent-Monolith (CRM, auth, LLM client)

Local repo: `D:\Phase 5(Internships)\Creatorcent-Monolith`, the user's earlier project.
- **Backend:** FastAPI, SQLAlchemy 2, Postgres.
- **Frontend:** TanStack Start, React 19, Tailwind 4, shadcn.

These notes were condensed on 2026-10-10. All paths below are relative to that repo. **Rule: copy individual classes and functions into fresh files. Never import the package:** `common/db/models.py` is 2261 lines and heavily coupled.

## Tender negotiation: copy the pattern, not the code
**Engagement (brand × creator deal) maps to Tender × Vendor bid.** Models are in `backend/common/db/models.py`:
- `Engagement` (1240-1331): `status`, `current_terms_version`, and `version` (used for optimistic locking).
- `EngagementParty` (1334): `side` (brand/creator/admin), `user_id`, `is_authoritative`.
- **`ProposalTerm` (1370-1401)**, the structured offer: `version` (unique per engagement), `commercials` JSON, `notes`, `proposed_by`, `status` (`proposed` / `agreed` / `superseded`).
- `EngagementMessage` (1434-1483), the thread: `author`, `party`, `body`, `type` (`human` / `system`), `channel`.
- `EngagementEvent` (1486), an append-only audit log of transitions and messages.
- `EngagementReadState` (1514), a per-user `last_read_at`. It drives unread counts, and there is no notifications table.

Status logic is in `backend/common/services/engagement_flow.py`:
- `_NEXT` (34-57) is the transition table, a dict of sets.
- `_TURN` (64-76) says whose move it is (brand / creator / both / admin). It drives the inbox buckets "needs your action / waiting / closed".
- `apply_transition` (272-312): assert the transition is legal (409 if not), set status, `version += 1`, record an event, post a system message "moved X → Y".

`backend/common/domain/state_machines.py` is a clean 75-line dict-of-sets with a 409 guard. Copy it outright.

### Things to fix when porting
- The router calls `apply_transition(enforce=False)`, so the state machine is **not enforced**. Use `enforce=True`.
- **There is no counter-offer endpoint**: `ProposalTerm` is created only once. Jal has to write accept / counter / reject. A counter inserts version `v+1` with price and quantity, marks the previous version `superseded`, moves to `negotiation`, and posts a system message.
- Don't lift the 855-line router (`common/routers/engagement_flow.py`), because it drags in Brand, Creator and Campaign. Rewrite it at about 200 lines.
- Drop approvals, the escrow states, channel bridging, and the campaign/tier coupling.

## Auth and roles
- **Near-lift:** `common/security/auth.py` (bcrypt + HS256 JWT, about 100 lines) and `common/security/deps.py` (`get_current_user`).
- Roles are a single enum column on User (`models.py:30-46`).
  - Jal mapping: `gov_admin`, `vendor` (with `org_id` pointing to the vendor company), `citizen`.
- **Patterns:** `common/security/tenancy.py` has a `TenantContext` and `scope_*` query filters that fail closed (`filter(false())`). `common/security/access.py` is a global per-app guard with `PUBLIC_PREFIXES`.
- **Do NOT copy `/auth/register`** (`common/routers/auth.py:72-105`). It takes `role` and `org_id` from the request body, so anyone can make themselves an admin of any org. Seed the gov and vendor accounts, and allow self-signup only for citizens.

## LLM client: lift nearly as-is
- `backend/common/services/llm/` is about 135 lines:
  - `base.py`: `LLMClient.structured(messages, json_schema) -> (dict, Usage)` and `complete()`.
  - `factory.get_llm_client()` switches on `LLM_PROVIDER`.
  - `openai_client.py` uses `response_format=json_schema`.
- **Jal adds a Bedrock client branch** (about 40 lines, boto3 `converse` with a tool/JSON schema). The existing client can't reach Bedrock.

## Frontend
- **Lift:** the shadcn primitives in `frontend/packages/ui/src/ui/*.tsx` and `chart.tsx` (recharts), plus `shared/DataTable.tsx`.
- **Copy:** `frontend/packages/lib/src/engagement-status.ts`, the role-aware label "Your turn / Waiting on X".
- **Use as patterns only:** the inbox and detail pages `frontend/packages/ui/src/engagements/*.tsx` (about 1100 lines, tied to its api-client types).
- **Avoid the toolchain:** TanStack Start + Lovable + Nitro needs a Node 22 pin and a postinstall patch. Use plain Vite with copied shadcn files.

## Nothing reusable for
- **Realtime:** none. The inbox polls every 8 seconds (`MessagesPage.tsx:236-245`), which is fine for a hackathon.
- **Email:** it uses the Gmail API with Celery and is tied to Google Workspace. If Jal needs email, use SES `send_email` via boto3.
- **Map and geo:** there are only text place names, no coordinates. Jal needs vendor lat/lng, a haversine radius filter, and a map library.
- **Deploy:** `build.sh` pushes to ECR, then deploys to EC2 with docker compose and Traefik on top of RDS. It works but has many moving parts. Skip Celery, Redis and beat.
