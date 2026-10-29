# Provisioning (Phase 3)

Developer-only steps to set up users, phones, and the desk token. Never commit PINs or tokens.

## Prerequisites

```powershell
cd D:\amgold
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
copy .env.example .env   # set JWT_SECRET and ADMIN_API_KEY to strong values
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Create owner, staff, 3 enrollment codes

```powershell
cd D:\amgold\backend
.\.venv\Scripts\Activate.ps1
python scripts\create_admin_codes.py `
  --owner owner --owner-pin 2468 --owner-name "Shop Owner" `
  --staff staff --staff-pin 1357 --staff-name "Counter" `
  --codes 3 --code-label "Shop phone" `
  --desk-label "Billing desk"
```

Save the printed **enrollment codes** and the **desk token** once.

Or via Swagger (`/docs`) with header `X-Admin-Key: <ADMIN_API_KEY>`:

1. `POST /v1/admin/users` — owner then staff  
2. `POST /v1/admin/enrollment-codes` × 3  
3. `POST /v1/admin/desk-clients`

## Phone enroll + login

1. App: enter enrollment code → `POST /v1/devices/enroll` → store `device_token` securely.  
2. `POST /v1/auth/login` with `X-Device-Token` + `{username, pin}` → store JWT.  
3. Later calls: `Authorization: Bearer <access>` + `X-Device-Token`.

Max **3** active devices (`MAX_DEVICES`).

## Revoke a lost phone

```powershell
python scripts\create_admin_codes.py --revoke-device <device-uuid>
```

Or `POST /v1/admin/devices/{id}/revoke` with `X-Admin-Key`.

Create a new enrollment code for the replacement phone.

## Honesty note

Token-based device binding is weaker than hardware-backed request signing / Play Integrity.
Those can be added later without changing screens (see AGENTS.md §9).
