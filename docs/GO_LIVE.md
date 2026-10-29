# AmGold go-live checklist

Single path from empty Railway project to first printed bill from a phone scan.

## 1. Railway API

- [ ] Create Railway project; add Postgres **with pgvector** (volume for data).
- [ ] Deploy API from `backend/` Dockerfile (`railway.json` health: `/health`).
- [ ] **Disable** sleep / scale-to-zero so the model stays warm.
- [ ] Region: closest available to India (e.g. Singapore if offered).
- [ ] Set usage limit + billing alert (Hobby first).

## 2. Environment secrets (Railway dashboard — never commit)

| Variable | Notes |
|---|---|
| `DATABASE_URL` | From Railway Postgres |
| `JWT_SECRET` | Long random |
| `ADMIN_API_KEY` | Long random; for provisioning only |
| `R2_ENDPOINT` | Cloudflare R2 S3 endpoint |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | R2 API token |
| `R2_BUCKET` | Public-read catalog photos |
| `R2_BACKUP_BUCKET` | Nightly `pg_dump` uploads |
| `R2_PUBLIC_BASE_URL` | `https://….r2.dev` or custom domain |
| `MODEL_NAME` | Default `facebook/dinov2-small` |
| Optional | `TOP_K`, `AMBIGUITY_MARGIN`, `MIN_CONFIDENCE`, `MAX_DEVICES=3`, `LOG_LEVEL` |

Confirm `GET https://<railway-host>/health` → `{"ok":true}`.

## 3. Cloudflare R2

- [ ] Create public-read bucket for photos + separate backup bucket.
- [ ] CORS if needed for browser tools; phones use HTTPS URLs directly.
- [ ] After bulk import, note storage size vs free tier.

## 4. Database + catalog

- [ ] Migrations run on deploy (`CREATE EXTENSION vector` in first migration).
- [ ] Bulk-import designs (or owner add via app later).
- [ ] Nightly backup job → `R2_BACKUP_BUCKET`; document restore in `RUNBOOK.md`.

## 5. Provision users, codes, desk token

```powershell
cd D:\amgold\backend
# against production DATABASE_URL / ADMIN_API_KEY
python scripts\create_admin_codes.py `
  --owner <owner_user> --owner-pin <pin> --owner-name "Shop Owner" `
  --staff <staff_user> --staff-pin <pin> --staff-name "Counter" `
  --codes 3 --code-label "Shop phone" `
  --desk-label "Billing desk"
```

- [ ] Save **enrollment codes** (≤3 phones) and the **desk token** (shown once).
- [ ] Or use Swagger `/docs` with `X-Admin-Key`.

See also `docs/PROVISIONING.md`.

## 6. Build and install the Android APK

```powershell
cd D:\amgold
.\scripts\build_release_apk.ps1 -ApiBaseUrl "https://YOUR-SERVICE.up.railway.app"
```

APK path is printed (typically `build\app\outputs\flutter-apk\app-release.apk`).

- [ ] Install on ≤3 approved phones.
- [ ] Each phone: enroll with a code → PIN login → open Scan.
- [ ] Settings → Check backend → green.

## 7. InvGen (billing desk)

InvGen changes live on branch `feature/amgold-connector` in `D:\invgen`.

- [ ] Checkout/build that branch on the shop PC (or merge when ready).
- [ ] Settings → **AmGold** tab → On.
- [ ] Paste Railway HTTPS URL + desk token from step 5.
- [ ] Poll ms `3000`; Auto-import **off**; never auto-prints.
- [ ] Sidebar → **Mobile Bills** shows connection status.
- [ ] Restart poller if URL/token change.

Do not restructure InvGen; feature stays reversible when `amgold_enabled=false`.

## 8. First bill smoke test

1. Phone: scan a known design → confirm match (if ambiguous, tap the exact one) → Add to bill.
2. Send to billing desk → status Queued / pending.
3. InvGen: Mobile Bills → Import → confirm lines → finalise → print.
4. Phone history: status moves toward Received / Imported.
5. Failure drill: airplane mode on send, desk closed, revoke a device.

## 9. Honesty / ops notes

- Token device binding is weaker than hardware-key signing; Play Integrity later.
- Photos use public-read UUID keys (low sensitivity catalog).
- Phone never computes tax; desk owns invoice totals.
- Rolled gold is never described as real gold in UI or PDFs.
