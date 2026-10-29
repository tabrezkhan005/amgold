# AmGold Architecture

Jewelry scan → match → bill. Flutter phone + FastAPI on **Railway** + InvGen Electron desk + **Cloudflare R2** for files.
Same Wi‑Fi on phone and desk is for convenience; **bills always go through the cloud relay** (phone → Railway → desk). No LAN HTTP between phone and InvGen.

## Components

| Piece | Role | Deploy |
|-------|------|--------|
| Flutter app | Camera scan, cart, send draft, owner enroll | Android APK on shop phone |
| FastAPI `api` | Auth, products, embeddings, scan match, bill drafts, desk poll | Railway (Docker, 1 replica) |
| Postgres + pgvector | Products, embeddings, devices, drafts, audit — **one** DB | Railway (`pgvector/pgvector` template) |
| Cloudflare R2 (public) | Product photos (1280) + thumbnails (400), UUID keys | R2 public-read bucket |
| Cloudflare R2 (private) | Nightly `pg_dump` backups, 14–30 day retention | Separate backup bucket |
| InvGen (Electron) | Local SQLite POS: products, customers, invoices, print | Windows desk PC (`D:\invgen`) |

## Network topology (same Wi‑Fi, cloud bills)

```
[Phone] ──HTTPS──► [Railway API] ──private──► [Railway Postgres+pgvector]
                         │
                         │  drafts (pending)
                         │  photos ──► [R2 public]
                         │  backups ─► [R2 private]
                         ▼
[Desk PC / InvGen] ◄──poll ~3s── GET /v1/desk/drafts + POST .../ack
                         │
                         ▼
              local SQLite invoice + thermal/A4 print
```

- Phone and desk may share shop Wi‑Fi as long as **both reach the internet**.
- InvGen does **not** listen for phone LAN calls. It polls Railway with a desk token.
- Desk sync **v1 = polling only** (~3 s, exponential backoff when unreachable). SSE endpoint may be added later; do not implement SSE in v1.
- Offline phone: queue draft locally; flush when online. Desk offline: drafts stay `pending` until ack.

## Auth

- Device enroll → device token; user login → JWT (`owner` | `staff`).
- Desk clients: `X-Desk-Token` (provisioned via admin API).
- Admin: `X-Admin-Key` (`ADMIN_API_KEY`).
- At most `MAX_DEVICES` (3) active phones.

## Data flow — scan

1. Phone captures image → `POST /v1/scan` (multipart).
2. API: preprocess → DINOv2 embedding → cosine top‑K via pgvector.
3. Response: matches, `ambiguous`, `low_confidence`, `scan_id`.
4. UI: never auto-select when ambiguous; require tap to confirm.

## Data flow — bill draft (cloud relay)

1. Phone `POST /v1/bills/drafts` with line items (`code`, `name`, `qty`, `unit_price`, …).
2. Server stores draft `pending`, returns draft id.
3. Desk polls `GET /v1/desk/drafts?status=pending` every ~3 s.
4. Operator **confirms** in InvGen billing UI (auto-import setting default OFF; never auto-print).
5. Desk `POST /v1/desk/drafts/{id}/ack` → `imported` | `failed`.

## Matching (non-negotiable)

- Embeddings + nearest neighbor — **not** a closed-set classifier.
- New SKU = enroll images + store embedding; no full retrain.
- Ambiguity / low confidence flags as in AGENTS.md §7.

## Hosting decisions

| Topic | Choice | Why |
|-------|--------|-----|
| Platform | Railway + Cloudflare R2 | AGENTS.md v3; RAM-friendly metering; R2 free tier fits ~2000 designs |
| Postgres | Railway **pgvector template** (`pgvector/pgvector:pg18`) | Official Railway docs: stock Postgres has **no** pgvector; templates ship the extension; migration runs `CREATE EXTENSION vector` |
| Embeddings | `vector(768)` in Postgres | Exact cosine search is fine for ~16k photo rows; HNSW only if p95 > 100 ms |
| API↔DB | Private `DATABASE_URL` (not `DATABASE_PUBLIC_URL`) | Avoid egress; Railway private networking |
| Sleep / scale-to-zero | **Disabled** | DINOv2 must stay loaded |
| Region | `asia-southeast1-eqsg3a` (Singapore) | Closest Railway Metal region to India |
| Replicas / workers | 1 replica, 1 Uvicorn worker | Single in-memory model |

Fallback if pgvector somehow unavailable: store embeddings as `bytea` / `real[]` and search in-memory with NumPy (cache at startup). **Not used** while the pgvector template is available.

## Prototype vs production (this repo)

| Area | Current prototype | Production target |
|------|-------------------|-------------------|
| Backend layout | Flat modules + local index | `api/v1`, `ml/`, `db/`, Postgres+pgvector |
| Auth | Optional API key | Device JWT + admin key + desk token |
| Bills | Local PDF only | Cloud drafts + InvGen connector (poll) |
| Storage | Local disk | R2 + local-disk fallback for dev |

## Trust boundaries

- Phone never writes InvGen SQLite.
- Desk never trusts phone IPs; only Railway + desk token.
- Secrets never committed; set in Railway / local `.env` only.
