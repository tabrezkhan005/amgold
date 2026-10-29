# AmGold

Private Flutter + FastAPI prototype: photograph a jewelry design, match it by
visual similarity, confirm look-alikes, and generate a PDF bill (₹).

Rolled gold is labelled as **rolled gold**, never as real gold.

Full contract: [`AGENTS.md`](AGENTS.md). Demo script: [`DEMO.md`](DEMO.md).

## Setup (under 10 steps)

1. **Flutter / Android SDK** already installed (`flutter doctor` clean).
2. **Backend venv + deps**
   ```powershell
   cd D:\amgold\backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   copy .env.example .env
   ```
3. **Set `API_KEY`** in `backend\.env`.
4. **Catalog** — sample file is already at `backend\data\products.json` (10 PLACEHOLDER products; P001/P002 are look-alikes).
5. **Photos** — put 5–8 JPEGs in each of:
   `backend\data\reference_photos\P001` … `P010` (vary angle/lighting; hand + tray).
6. **Build index**
   ```powershell
   python scripts\validate_catalog.py
   python scripts\build_index.py
   ```
7. **Run API** (binds all interfaces for phone access)
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
8. **Firewall** (once): allow TCP 8000 inbound. Find laptop IP with `ipconfig`.
9. **Flutter deps**
   ```powershell
   cd D:\amgold
   flutter pub get
   ```
10. **Run on phone** (same Wi-Fi as laptop)
    ```powershell
    flutter run --release --dart-define=API_BASE_URL=http://<LAPTOP_IP>:8000 --dart-define=API_KEY=<same-as-.env>
    ```

Login: `staff` / `amgold`

## Useful commands

```powershell
# Backend tests
cd D:\amgold\backend
.\.venv\Scripts\Activate.ps1
pytest -q
python scripts\evaluate.py

# Flutter
cd D:\amgold
flutter analyze
flutter test
```

## Layout

- `lib/` — Flutter app
- `backend/` — FastAPI recognition API
- `docs/` — Architecture + InvGen Electron integration
- `assets/fonts/` — Noto Sans for ₹ in PDFs

## Production delivery (deploy → distribute → go live)

**Follow this first:** [`docs/GO_LIVE.md`](docs/GO_LIVE.md)

Phone and desk can share shop Wi‑Fi. Bills always go:

**phone → Railway API → InvGen desk** (poll ~3 s + ack). No phone→desk LAN. No SSE in v1.

```powershell
# After Railway URL exists — build the shop APK
cd D:\amgold
.\scripts\build_release_apk.ps1 -ApiBaseUrl "https://YOUR-SERVICE.up.railway.app"
```

- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- InvGen mapping: [`docs/ELECTRON_INTEGRATION.md`](docs/ELECTRON_INTEGRATION.md)
- Deploy detail: [`docs/DEPLOY_RAILWAY.md`](docs/DEPLOY_RAILWAY.md)
- Provisioning: [`docs/PROVISIONING.md`](docs/PROVISIONING.md)
- Desk app: `D:\invgen` branch `feature/amgold-connector` — see `docs/AMGOLD_DESK.md` there
- Env templates: [`.env.example`](.env.example), [`backend/.env.example`](backend/.env.example)

### Local Postgres (pgvector)

```powershell
cd D:\amgold
docker compose up -d
cd backend
copy .env.example .env
# DATABASE_URL uses localhost:5433 (avoids Windows Postgres on 5432)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
