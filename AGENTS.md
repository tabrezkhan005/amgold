# AGENTS.md — AmGold (Production)

Read this file fully before doing anything. It is the source of truth.
If a request conflicts with it, stop and ask. Rename this file to `AGENTS.md` in the
project root (replacing the prototype version). Hosting: Railway + Cloudflare R2.

---

## 1. Product summary

AmGold is a private Android app for a supplier of designer ornaments (rolled gold, which is
NOT real gold, plus necklaces, chains, earrings and similar). The catalog has about 2000
designs, many of them near look-alikes (e.g. the same necklace with 8 vs 10 beads).

What the client can do, entirely from the phone:
1. **Scan** any design with the camera and get its price and details instantly, with
   look-alike designs shown for confirmation.
2. **Add new products** by photographing them (guided capture) and entering the details.
   The product is saved to the database and is immediately recognisable by the scanner.
3. **Edit** prices, details and photos; deactivate discontinued designs.
4. **Build a bill** with editable quantities and **send it directly to the client's existing
   Electron invoice/billing desktop software**, which prints the invoice.

The app is installed on at most **3 approved phones**.

## 2. Roles

| Role | Who | Can do |
|---|---|---|
| Owner | the client | scan, bill, add/edit products, review scan corrections, view devices |
| Staff | shop staff | scan, bill |
| Admin | the developer | provision devices and users, revoke devices, via admin API (not in the app) |
| Desk | the Electron app | read pending bill drafts, acknowledge them |

## 3. Architecture

```
 Flutter app (≤3 phones)  ──HTTPS──►  FastAPI on Railway  ◄──HTTPS──  Electron invoice app
   • camera, scan, bill                • recognition (DINOv2)           • "Mobile Bills" inbox
   • owner product wizard              • auth + device binding          • imports draft → invoice
   • local catalog cache (Drift)       • bill-draft relay               • prints
                                              │
                          ┌───────────────────┴───────────────────┐
                    Railway Postgres (pgvector)       Cloudflare R2 (S3-compatible)
                    products, vectors, users,         product photos + thumbnails
                    devices, drafts, logs
```

Key decisions (do not change without asking):
- Recognition = **image embeddings + nearest-neighbour search**, never an N-class classifier.
- Bills reach the Electron app through a **cloud relay of bill drafts** (the phone and the
  desktop never talk directly). This works from any network and survives either side being
  offline. Direct LAN connection was rejected as fragile.
- Single backend instance (one model in memory). Do not design for multi-instance scaling.

## 4. Hosting (Railway + Cloudflare R2)

- **API service (Railway):** deployed from the `backend/` Dockerfile via the GitHub repo.
  Railway bills for actual resource use, and RAM is the main cost, so the model's memory
  footprint matters. Measure real memory in production; if the model plus runtime exceeds
  about 1.5 GB, switch inference to ONNX Runtime (optionally quantised) with verified parity.
- **Never enable app sleeping / serverless scale-to-zero** on the API service. The model must
  stay loaded, otherwise the first scan after idle time is very slow.
- **Database (Railway Postgres with pgvector):** use a Postgres service that includes the
  `pgvector` extension (Railway's pgvector template or a `pgvector/pgvector` image; verify the
  current option in Railway's docs). First migration runs `CREATE EXTENSION vector`. Add a
  Railway volume for data. **Backups:** nightly `pg_dump` (cron service or scheduled job)
  uploaded to a separate R2 bucket, and document how to restore. Do not rely on the database
  service alone as the only copy.
- **Photos (Cloudflare R2):** S3-compatible via `boto3`, public-read bucket (r2.dev URL or a
  custom domain) with UUID keys. R2's free allowance (10 GB storage, 1 million write-class and
  10 million read-class operations per month) comfortably covers about 2000 designs at roughly
  8 photos each plus thumbnails; estimate the real size during bulk import and report it.
- **Region:** choose the Railway region closest to India that is available (Singapore if
  offered). Confirm in the dashboard.
- **Plan and cost control:** start on Railway Hobby; move to Pro only if usage consistently
  approaches the Pro minimum or support/availability guarantees are needed. Set a usage limit
  and billing alert so a bug cannot run up a surprise bill. Report the observed monthly usage
  after the first week.
- **Model weights:** download during the Docker build so they are baked into the image
  (no download at startup). Run a warm-up inference at startup so the first scan is fast.
- **Config:** `Dockerfile` plus `railway.json` (build/deploy settings, health check path
  `/health`, restart policy) and environment variables set in the Railway dashboard (secrets
  never committed). Verify field names against Railway's current docs; do not rely on memory.
- **Process:** one Uvicorn worker. CPU-bound inference runs in a thread pool behind a
  semaphore (max 2 concurrent) so the event loop stays responsive.
- **TLS:** Railway provides HTTPS on its generated domain (custom domain optional). Remove all
  cleartext/HTTP allowances from the app.

Environment variables:
`DATABASE_URL`, `JWT_SECRET`, `ADMIN_API_KEY`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_BACKUP_BUCKET`, `R2_PUBLIC_BASE_URL`,
`MODEL_NAME` (default `facebook/dinov2-small`), `TOP_K` (5), `AMBIGUITY_MARGIN` (0.05),
`MIN_CONFIDENCE` (0.50), `MAX_DEVICES` (3), `SAVE_SCAN_IMAGES` (ambiguous_only),
`LOG_LEVEL`. Provide `.env.example`. Never commit real values.

## 5. Repository layout

```
amgold/                              # D:\amgold  (Flutter project root)
├── AGENTS.md  README.md  .gitignore  railway.json  docker-compose.yml
├── pubspec.yaml
├── assets/fonts/                    # Noto Sans (for ₹ in any generated PDF)
├── lib/
│   ├── main.dart  app.dart
│   ├── core/{config, theme, network, router, storage, utils}/
│   ├── data/{db(drift), repositories, models}/
│   └── features/{auth, scan, results, product, catalog, owner, bill, settings}/
├── test/  integration_test/
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  deps.py
│   │   ├── api/v1/{auth, devices, products, scan, bills, desk, admin, health}.py
│   │   ├── core/{security.py, rate_limit.py, errors.py}
│   │   ├── db/{base.py, models.py, session.py}
│   │   ├── ml/{embedder.py, preprocess.py, search.py, enroll.py}
│   │   ├── services/{storage.py, catalog.py, drafts.py, scans.py}
│   │   └── schemas/
│   ├── alembic/  alembic.ini
│   ├── scripts/{bulk_import.py, evaluate.py, validate_catalog.py, create_admin_codes.py,
│   │            export_onnx.py}
│   ├── tests/
│   ├── Dockerfile  requirements.txt  .env.example  README.md
└── docs/{ARCHITECTURE.md, ELECTRON_INTEGRATION.md, DEPLOY_RAILWAY.md, PROVISIONING.md, RUNBOOK.md, API.md}
```

The Electron app lives in a separate folder (path given by the developer). Changes to it
are limited to one isolated module (see section 10) and must not break existing printing.

## 6. Database schema (PostgreSQL, SQLAlchemy 2.0 + Alembic migrations)

- `users`: id uuid pk, username unique, display_name, role (owner|staff), pin_hash,
  is_active, failed_attempts, locked_until, created_at
- `devices`: id uuid pk, label, platform, app_version, token_hash, status (active|revoked),
  registered_at, last_seen_at, revoked_at
- `enrollment_codes`: id, code_hash, label, expires_at, used_at, used_by_device_id, created_at
- `products`: id uuid pk, code text unique (human code, e.g. `AMG-0001`, auto-generated,
  editable only by owner), name, category (necklace|chain|earring|bangle|ring|pendant|other),
  material (default `rolled_gold`), price numeric(10,2), weight_g numeric, description,
  difference_note, hsn_code null, gst_rate null, unit default `pcs`, in_stock bool,
  is_active bool, primary_photo_id, created_by, created_at, updated_at
- `product_photos`: id uuid pk, product_id fk, storage_key, thumb_key,
  `embedding vector(768)`, embedding_model, preprocessing_version,
  source (enrollment|correction|import), created_at
- `product_links`: product_id, similar_product_id, note (stored in both directions)
- `price_history`: id, product_id, old_price, new_price, changed_by, changed_at
- `scans`: id uuid, device_id, user_id, created_at, top_product_id, top_score, margin,
  ambiguous, low_confidence, latency_ms, image_key null, chosen_product_id null
- `bill_drafts`: id uuid pk (equals the client-generated draft id, for idempotency),
  created_by_user, device_id, customer_name, customer_phone, notes, discount_amount,
  items jsonb, status (pending|delivered|imported|failed|cancelled), created_at,
  delivered_at, imported_at, desk_invoice_ref, failure_reason
- `desk_clients`: id, label, token_hash, last_seen_at
- `audit_log`: id, actor_type, actor_id, action, entity, entity_id, data jsonb, at

Indexes: product code, product `updated_at`, `product_photos.product_id`, draft status.
Vector search starts as exact search (no ANN index; 2000 designs × ~8 photos is small).
Benchmark it. Add an HNSW index only if search p95 exceeds 100 ms.
Prices are never stored as floats. Draft items snapshot price and name at send time.

## 7. Recognition pipeline

### 7.1 Preprocessing (ONE shared function for indexing, enrollment and querying)
1. Open with Pillow and apply `ImageOps.exif_transpose` (phone orientation).
2. Convert to RGB.
3. Pad to square with neutral gray (128,128,128). Never center-crop.
4. Resize to 224×224 (bicubic).
5. Normalise via the model's image processor with `do_resize=False`, `do_center_crop=False`.
Version this as `preprocessing_version`. Rows with a different model or version than the
running code must be flagged and re-embedded by a reindex job; the server refuses to
silently mix versions.

### 7.2 Embedding
DINOv2 via `transformers`: concatenate the CLS token and the mean of the patch tokens,
L2-normalise, `float32`. Model loaded once at startup, `eval()`, `torch.no_grad()`,
warm-up inference at boot. Keep `MODEL_NAME` configurable (`dinov2-base` is the upgrade).
Optional test-time augmentation (average embeddings of the image and 1 to 2 mild crops) is
implemented behind a flag and enabled only if `evaluate.py` shows it helps.

### 7.3 Search
Cosine similarity via pgvector. Take the best score per product (max over its photos;
evaluate whether mean-of-top-2 is more robust). Return `TOP_K`.
**Look-alike injection:** siblings listed in `product_links` for the top product are
appended (`source: "catalog_similar"`) with their own computed score if not already present.
Flags: `ambiguous` if top1−top2 < `AMBIGUITY_MARGIN` or a linked sibling scores within the
margin; `low_confidence` if top1 < `MIN_CONFIDENCE`. Thresholds are tuned with real data
(section 12), not guessed.

### 7.4 Enrollment (adding a new product)
1. App uploads 4 to 10 guided photos plus details.
2. **Pre-check** (`/v1/products/precheck`): embed the photos, search the catalog, return the
   closest existing products with scores and `duplicate_suspected`. The app shows
   "Looks similar to AMG-0123. New design or variant?" The owner can link it as a look-alike
   and write the `difference_note` (e.g. "8 beads").
3. Save: store processed photos (max 1280 px) and thumbnails (400 px) in R2, compute and
   store embeddings, insert rows, write audit log. Searchable immediately.
4. **Verification scan:** the app asks the owner to scan the new item once. If it does not
   rank first, the app asks for more photos. A product is only marked "verified" after this.
5. Minimum 3 photos accepted (warn below 5). Server-side quality checks (blur via Laplacian
   variance, too dark/bright, too small) return warnings the app shows per photo.

### 7.5 Corrections loop
`POST /v1/scan/{id}/feedback` records which product staff finally chose. Cases where the
choice differs from the top match appear in an owner-only **Scan review** screen with the
query photo; the owner can promote the scan to a reference photo of the chosen product
(`source: "correction"`). This is how accuracy improves on the real shop's lighting.
Query images are stored only for ambiguous, low-confidence or corrected scans, with a
30-day retention job.

## 8. API v1 contract

JSON is `snake_case`. Errors are `{"detail": "...", "code": "..."}` with proper status codes.
Header on every request except enrollment, health and admin: `Authorization: Bearer <jwt>`
plus `X-Device-Token: <device token>`. Every response must be fast, small and cache-friendly.

**Public:** `GET /health` → `{"ok": true}` (no internals).

**Device and auth**
- `POST /v1/devices/enroll` `{code, label, platform, app_version}` → `{device_id, device_token}`.
  Fails if 3 active devices already exist or the code is used/expired.
- `POST /v1/auth/login` `{username, pin}` (requires a valid device token) →
  `{access_token, refresh_token, expires_in, user}`. Rate-limited, lock after repeated failures.
- `POST /v1/auth/refresh`, `GET /v1/me`.

**Admin** (header `X-Admin-Key`): `POST /v1/admin/enrollment-codes`,
`GET /v1/admin/devices`, `POST /v1/admin/devices/{id}/revoke`, `POST /v1/admin/users`,
`POST /v1/admin/users/{id}/reset-pin`, `POST /v1/admin/desk-clients` (returns token once),
`POST /v1/admin/reindex`, `GET /v1/admin/health` (detailed: model, vectors, memory).

**Catalog**
- `GET /v1/products?updated_since=&q=&category=&limit=&cursor=` — delta sync. Includes
  tombstones for deactivated products so the app can remove them.
- `GET /v1/products/{id}`
- `POST /v1/products/precheck` (owner, multipart `photos[]`)
- `POST /v1/products` (owner, multipart: fields + `photos[]`)
- `PATCH /v1/products/{id}` (owner; price changes write `price_history`)
- `POST /v1/products/{id}/photos`, `DELETE /v1/products/{id}/photos/{photo_id}`
- `POST /v1/products/{id}/deactivate`, `POST /v1/products/{id}/links`

**Scan**
- `POST /v1/scan` (multipart `image`) →
```json
{"scan_id":"uuid","matches":[{"product_id":"uuid","code":"AMG-0001","score":0.8712,
 "rank":1,"source":"visual","product":{...compact product...}}],
 "top_score":0.8712,"margin":0.0292,"ambiguous":true,"low_confidence":false,
 "latency_ms":210}
```
- `POST /v1/scan/{scan_id}/feedback` `{chosen_product_id}`
- `GET /v1/scan/review` (owner), `POST /v1/scan/{scan_id}/promote` (owner)

**Bill drafts (phone side)**
- `POST /v1/bills/drafts` `{client_draft_id, customer_name?, customer_phone?, notes?,
  discount_amount?, items:[{product_id, code, name, unit_price, quantity, unit,
  hsn_code?, gst_rate?}]}` → draft with status. Idempotent on `client_draft_id`.
- `GET /v1/bills/drafts?limit=`, `GET /v1/bills/drafts/{id}`, `POST /v1/bills/drafts/{id}/cancel`
  (only while `pending`).

**Desk side (Electron; header `X-Desk-Token`)**
- `GET /v1/desk/drafts?status=pending` — **v1 desk sync is polling only** (~3 s client-side,
  exponential backoff when unreachable).
- `POST /v1/desk/drafts/{id}/ack` `{status: "imported"|"failed", invoice_ref?, reason?}`
- `GET /v1/desk/drafts/stream` — **reserved for a later SSE phase**; shape the router so it can
  be added without breaking poll clients. Do **not** implement SSE in v1.

Draft status machine: `pending → delivered (desk fetched it) → imported | failed`;
`pending → cancelled`. Status changes are visible to the phone (poll or push-on-open).

## 9. Auth and device binding

- Developer creates one-time **enrollment codes** (hashed in DB, expire in 48 h). A phone
  enters a code on first launch and receives a **device token** that is stored in
  `flutter_secure_storage` (Android Keystore-backed). The server hashes it and enforces at
  most `MAX_DEVICES` active devices. Revoked devices are rejected immediately.
- Users sign in with username + PIN (hashed with argon2 or bcrypt), allowed only from an
  active device. Short-lived access JWT plus refresh token. Rate limit and lockout.
- Design the network layer so hardware-backed request signing (Android Keystore keypair)
  and Play Integrity can be added later without changing screens. Be honest in docs that
  token-based binding is weaker than hardware-key signing.
- Every owner action (create/edit product, price change, promote photo) is audit-logged.
- Do not log tokens, PINs or API keys.

## 10. Electron integration (billing desk)

The existing Electron invoice generator is the system of record for printed invoices
and tax calculation. The phone only sends **what was sold and how many**.

- **Phase 0 audit is mandatory:** read the Electron codebase (framework, main/renderer
  split, how invoices and items are stored, how printing works, any existing item master,
  how settings are stored) before designing anything. Write the findings and the proposed
  field mapping to `docs/ELECTRON_INTEGRATION.md`, then ask me to confirm.
- Add **one isolated module** (e.g. `amgold-connector`) in the Electron main process:
  - Settings: backend URL and desk token (stored securely), connection status, auto-import
    toggle (default **off**). Never auto-print.
  - **v1: polling only** (~3 s) with exponential backoff when the backend is unreachable and a
    status indicator in settings. Do not implement SSE in the desk client for v1 (API may add
    `/v1/desk/drafts/stream` later).
  - A **"Mobile Bills" inbox** shows pending drafts (customer, items, quantities, time).
    "Import" opens the existing invoice screen pre-filled with the items; the operator must
    confirm, edit if needed, finalise and print. Auto-import (when enabled) only pre-fills /
    creates the local draft — still no auto-print.
  - Default line price = draft (phone quote). Badge lines where InvGen catalog price differs;
    operator may switch per line. Never overwrite InvGen product master prices. Missing SKU →
    custom line + optional "Create product in InvGen".
  - De-duplicates by draft id, acknowledges with `imported` plus the local invoice reference,
    or `failed` with a reason.
  - Works if the internet drops: drafts stay `pending` on the server and are picked up later.
  - Feature-flagged so the app behaves exactly as before when disabled.
- Do not restructure the Electron app. Create a git branch (or back up) before editing.
  Keep changes minimal, reversible and documented.
- Item mapping: `code`→item code/SKU, `name`→description, `unit_price`→rate (draft default),
  `quantity`→qty, `unit`→unit. Optional draft `hsn_code`/`gst_rate` are **ignored in v1**;
  InvGen uses its invoice-level `tax_rate`. Do not change InvGen's schema for HSN/GST.
  Tax and totals are computed by Electron, not by the phone.

## 11. Flutter specification

### 11.1 Stack
Flutter stable (as installed), null-safe Dart. Add packages with `flutter pub add` and read
their current docs on pub.dev; never guess APIs from memory (especially `camera`,
`shadcn_ui`, `drift`). Planned packages: `flutter_riverpod`, `go_router`, `dio`, `camera`,
`drift` + `sqlite3_flutter_libs`, `flutter_secure_storage`, `cached_network_image`,
`flutter_image_compress`, `image_picker` (fallback only), `flutter_animate`, `google_fonts`,
`shadcn_ui` (fall back to custom Material 3 if unstable), `intl`, `connectivity_plus`,
`uuid`, `package_info_plus`, `pdf` + `printing` (optional fallback invoice). Ask before
adding anything else.

### 11.2 Architecture
Feature-first folders, Riverpod for state, repository pattern over `ApiClient` and Drift.
No business logic in widgets. Immutable models. Typed `ApiException` with friendly messages.
Build config via `--dart-define=API_BASE_URL=...` (production HTTPS URL). No hardcoded URLs
or secrets.

### 11.3 Offline-first catalog
- On login, delta-sync products into Drift (`updated_since`), including tombstones.
  Product details therefore open **instantly** after a scan, from the local cache.
- Thumbnails and photos cached with `cached_network_image` using the photo id as cache key.
- **Outbox pattern for bill drafts:** if the network fails, the draft is saved locally and
  retried with backoff. The UI shows a status chip: Queued / Sent / Received by desk /
  Imported / Failed. The cart persists across app restarts.
- Scanning requires the network (recognition is server-side). Show a clear offline state with
  manual catalog search still working from the cache.

### 11.4 Screens
1. **Enroll + Login:** first launch asks for the enrollment code; afterwards username + PIN.
   Show a clear "device not approved / revoked" state.
2. **Scan:** camera pre-initialised after login and kept alive between screens. Focus frame,
   scanning animation, flash, tap-to-focus, torch hint, capture button, manual-search entry.
   **Crop the capture to the frame region on device** so the item fills the image, then
   compress (~800 px long edge, JPEG ~85) in an isolate. Run on-device quality checks
   (blur, brightness) and prompt "Hold steady" or "Need more light" before uploading.
   Handle permission denied, lifecycle pause/resume, and init failure. Portrait only.
3. **Results:** top matches as swipeable cards (thumbnail, name, code, price, confidence).
   States: *clear match* (top card emphasised; still requires a tap), *ambiguous* (banner
   "Close matches. Confirm the exact design" plus side-by-side compare sheet with the
   `difference_note`; NEVER auto-select), *low confidence* ("No confident match", Retake or
   Search manually). Skeleton loaders, Hero transition, friendly retry on errors.
   Send scan feedback with the chosen product.
4. **Product detail:** gallery, name, code, price (₹, Indian grouping), weight, material
   (display truthfully, e.g. "Rolled gold"), description, difference note, similar designs,
   **editable quantity** (stepper plus tap-to-type, long-press to repeat, min 1, max 999),
   Add to bill with haptic feedback. Owner sees Edit.
5. **Catalog:** searchable, filterable grid from the local cache (owner and staff).
6. **Owner: Add product wizard:** guided capture of photos (front, back or clasp, close-up of
   detail, angled, flat on tray, in hand) with per-photo quality warnings → duplicate/
   look-alike pre-check with link-as-similar and difference note → details form (name,
   category, material, price, weight, description, optional HSN/GST) → review → save with
   progress → verification scan. Include a **Rapid add** mode (minimum photos, auto-advance)
   because 2000 designs is a lot.
7. **Owner: Edit product:** quick price edit, manage photos, links, deactivate. Price edits
   ask for confirmation.
8. **Owner: Scan review:** list of corrected scans with "Add as reference photo".
9. **Bill:** line items with editable quantity (swipe to remove), optional customer name and
   phone, optional discount and notes, running total shown as an indication ("final tax and
   total are calculated at the billing desk"), **Send to billing desk** with a confirmation
   sheet and animated status, then a "Start new bill" action. Bill history with statuses.
10. **Settings:** user, device label, app version, backend status, logout, optional
   "export last bill as PDF" fallback.

### 11.5 Design system
Premium jewelry-boutique feel. Dark charcoal `#1A1A1A` with cream `#F7F2E8` surfaces (or a
cream light theme, one chosen and consistent), gold accent `#C9A24B`. Playfair Display for
headings and prices, Inter for body via `google_fonts`. Material 3 with a custom
`ColorScheme`, no default blue. Spacing 4/8/12/16/24/32, card radius 16, touch targets ≥ 48 dp.
All colors, text styles and spacing come from theme tokens. Motion: `flutter_animate`,
150 to 300 ms, skeletons not spinners, haptics on capture and add-to-bill. Minimal typing.
Staff are handling jewelry while using the phone, so make buttons large and states obvious.

## 12. Performance and accuracy targets

These are goals to measure against, not guarantees.
- Capture → results on screen: p50 ≤ 1.5 s, p95 ≤ 3 s on a normal mobile connection
  (server-side embed+search ≤ 500 ms on the Railway service).
- Product detail from scan result: instant (local cache). Cold app start ≤ 2.5 s to camera.
- 60 fps scrolling and transitions in `--release` on the client's actual phones.
- Warm-up request at app start so the server is never cold when the first scan happens.
- Accuracy on the real catalog via leave-one-photo-out `evaluate.py`: initial targets
  top-3 ≥ 98%, top-1 ≥ 90%, and for known look-alike pairs the correct design must appear
  in the top 2 with `ambiguous` raised in ≥ 95% of cases. Report actual numbers honestly;
  if targets are missed, follow the improvement ladder: better reference photos →
  `dinov2-base` / higher resolution → threshold tuning → TTA → patch-level re-ranking of the
  top candidates when ambiguous → fine-tuning with triplet loss using the look-alike pairs
  as hard negatives (only if still needed, as a separate scoped task).

## 13. Security and privacy
HTTPS only. Hash tokens, PINs and codes. Rate-limit login, enrollment and scan endpoints.
Validate uploads (type, size ≤ 10 MB, decodable image). CORS restricted. No secrets in the
repo or app binary except the production API base URL. Photos use unguessable UUID keys in a
public-read bucket (catalog photos are low sensitivity; note this trade-off in the docs).
Customer name/phone are personal data: keep drafts for a documented retention period.

## 14. Testing and QA
- Backend: `pytest` for preprocessing, search ranking and look-alike injection, ambiguity
  logic, enrollment and precheck, auth, device limit (4th device rejected), revoked device,
  draft idempotency and status transitions, desk ack flow, upload validation.
- Flutter: unit tests for models, cart/quantity logic, outbox retry, ambiguous-state UI;
  at least one integration test of login → add to bill → send.
- End-to-end on real phones in `--release`, on mobile data and on Wi-Fi.
- Failure drills: server asleep/slow, no internet during send, Electron app closed, camera
  permission denied, revoked device, duplicate send tap.

## 15. Conventions
- `flutter analyze` and `ruff` (or flake8) clean. Small functions, no dead code.
- Migrations for every schema change. Never edit applied migrations.
- Conventional commit-sized changes; after each task state what changed, how to run, how to verify.
- `.gitignore` covers `.env`, `.venv`, keystores (`*.jks`, `key.properties`), build outputs.
- Never invent product data, prices or photos. Use clearly labelled placeholders.

## 16. Never do
- Never use an N-class classifier for recognition.
- Never auto-select or auto-add a product when `ambiguous` is true.
- Never describe rolled gold as real gold anywhere (UI, PDFs, seed data, copy).
- Never use different preprocessing for query vs index.
- Never compute tax or finalise totals on the phone; Electron owns that.
- Never hardcode secrets, tokens or URLs. Never commit the Android keystore.
- Never restructure the Electron app or break its existing print flow.
- Never add dependencies silently or guess a package API from memory.
- Never claim something works unless you ran it. If you could not, say so.
- Never block the event loop with inference; never load the model per request.

## 17. Out of scope for now
Multi-shop/multi-tenant, iOS build, web admin dashboard, GST reports, stock counting,
thermal printing from the phone, hardware-key request signing, Play Integrity (design for it,
do not build it yet).
