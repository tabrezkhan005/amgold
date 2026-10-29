# AmGold API (backend)

FastAPI + DINOv2 + Postgres/pgvector + Cloudflare R2.

## Local

```powershell
cd D:\amgold
docker compose up -d
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`GET /health` → `{"ok": true}`

Without R2 env vars, uploads use `STORAGE_LOCAL_DIR` (`data/storage`).

## Tests

```powershell
pytest -q
```

DB session tests skip if Postgres is not on `localhost:5433` (docker-compose maps host 5433).

## Provisioning (users / devices)

See [`docs/PROVISIONING.md`](../docs/PROVISIONING.md).

```powershell
python scripts\create_admin_codes.py `
  --owner owner --owner-pin 2468 `
  --staff staff --staff-pin 1357 `
  --codes 3 --desk-label "Billing desk"
```

## Deploy

See [`docs/DEPLOY_RAILWAY.md`](../docs/DEPLOY_RAILWAY.md). Railway Root Directory = `backend`.
