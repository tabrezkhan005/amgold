# Deploy AmGold API on Railway + Cloudflare R2

Verified against Railway docs (config-as-code, regions, cost control, pgvector template)
and Cloudflare R2 docs (S3 API + boto3 + public buckets) as of late 2026.

**Region:** prefer **Southeast Asia Metal — Singapore** (`asia-southeast1-eqsg3a`), closest to India.

**pgvector choice:** Railway’s **standard Postgres does not include pgvector**. Use a
**pgvector template** (image `pgvector/pgvector:pg18` / `pg16`). First migration runs
`CREATE EXTENSION IF NOT EXISTS vector`. Embeddings live in Postgres as `vector(768)`.
Fallback (NumPy in-memory) is **not** used while the template is available.

---

## 1. Cloudflare R2 (two buckets)

1. Cloudflare Dashboard → **R2** → create:
   - `amgold-media` — product photos + thumbnails (public-read later)
   - `amgold-backups` — **private** nightly `pg_dump` (keep private)
2. **API token:** R2 → Overview → **Manage** API Tokens → Create Account API token  
   Permission: Object Read & Write, scoped to both buckets.  
   Copy **Access Key ID**, **Secret Access Key**, and endpoint:
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
3. **Public media bucket:** open `amgold-media` → Settings → enable **Public Development URL**
   (`*.r2.dev`) for early testing, or attach a **custom domain** for production.  
   Set `R2_PUBLIC_BASE_URL` to that public base (no trailing slash).
4. Leave `amgold-backups` private (no public URL).

Official refs: [R2 S3 API](https://developers.cloudflare.com/r2/get-started/s3/),
[boto3](https://developers.cloudflare.com/r2/examples/aws/boto3/),
[public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/).

---

## 2. Railway project

1. Create a Railway account; start on **Hobby** ($5/mo includes $5 usage).
2. New **Project** → empty (or from GitHub after step 4).
3. **Preferred region:** Account / service Settings → Regions →
   **Southeast Asia Metal** (`asia-southeast1-eqsg3a`).  
   Ref: [Regions](https://docs.railway.com/deployments/regions).

### 2a. Postgres with pgvector

1. In the project: **+ New** → **Template** → search **pgvector**  
   (e.g. [Deploy pgvector](https://railway.com/deploy/pgvector) or **pgvector-pg18**).  
   Official guide: [RAG + pgvector](https://docs.railway.com/guides/rag-pipeline-pgvector)
   (“Railway's standard Postgres image does not include pgvector”).
2. After deploy, open the Postgres service → **Variables**. Note:
   - `DATABASE_URL` — **private** URL for other Railway services (use this on `api`)
   - `DATABASE_PUBLIC_URL` — only for laptop/`psql` from outside
3. Confirm a volume is attached for data persistence (templates usually do).
4. Rename the service to `postgres` if you like (optional).

### 2b. API service

1. **+ New** → **GitHub Repo** → select the AmGold repo.
2. Service settings:
   - **Root Directory:** `backend`
   - **Config file:** `/backend/railway.json` (absolute path in repo)
   - Builder: Dockerfile (auto if `Dockerfile` present)
3. **Do not enable Serverless / app sleeping**  
   Settings → Deploy → Serverless → leave **off**. The DINOv2 model must stay loaded.  
   Ref: [Cost control → Enabling serverless](https://docs.railway.com/pricing/cost-control).
4. Replicas: **1** (already in `railway.json` `multiRegionConfig`).
5. Health check: `/health` (in `railway.json`; timeout 300s for cold model start).

### 2c. Wire private networking

On the **api** service → Variables, add (use Railway variable references):

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | `${{postgres.DATABASE_URL}}` (exact service name may differ) |
| `JWT_SECRET` | long random string |
| `ADMIN_API_KEY` | long random string |
| `R2_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID` | from R2 token |
| `R2_SECRET_ACCESS_KEY` | from R2 token |
| `R2_BUCKET` | `amgold-media` |
| `R2_BACKUP_BUCKET` | `amgold-backups` |
| `R2_PUBLIC_BASE_URL` | `https://pub-….r2.dev` or custom domain |
| `MODEL_NAME` | `facebook/dinov2-small` |
| `TOP_K` | `5` |
| `AMBIGUITY_MARGIN` | `0.05` |
| `MIN_CONFIDENCE` | `0.50` |
| `MAX_DEVICES` | `3` |
| `SAVE_SCAN_IMAGES` | `ambiguous_only` |
| `LOG_LEVEL` | `INFO` |
| `LOAD_EMBEDDER` | `true` |

Use the **private** `DATABASE_URL`, not `DATABASE_PUBLIC_URL`, to avoid egress charges.  
Ref: [Cost control → private networking](https://docs.railway.com/pricing/cost-control).

Generate a public HTTPS domain: api service → Settings → Networking → **Generate Domain**.

---

## 3. Migrations

After the first successful deploy (or via one-off shell):

```bash
# Railway CLI, linked to the api service
railway run alembic upgrade head
```

Or add a **pre-deploy command** later: `alembic upgrade head`  
(see Railway `preDeployCommand` in config-as-code). First boot of a heavy image can be slow;
healthcheck timeout is 300s for that reason.

Confirm:

```bash
curl https://<your-domain>/health
# {"ok":true}
```

### Inference performance (scan + add-product)

Docker bakes an **ONNX** DINOv2-small embed graph (`INFERENCE_BACKEND=onnx`). Build tries
dynamic INT8 quantization and **keeps FP32** if torch↔ONNX cosine parity is below 0.999
(common for DINOv2). Scan uses `embed_async` (thread pool); enroll runs up to **2**
preprocess+embed+R2 workers.

In Railway **amgold → Logs**, look for:

- `embedder_backend=onnx` (or `torch` fallback) at startup
- `scan_timing embed_ms=… search_ms=… total_ms=…`
- `enroll_photos done … wall_ms=…`

Local export / parity:

```bash
cd backend
python scripts/export_onnx.py --out models/dinov2-small-embed.onnx --quantize
pytest tests/test_onnx_parity.py -q
```

Optional env: `TORCH_NUM_THREADS`, `ORT_INTRA_OP_THREADS`, `INFERENCE_BACKEND=torch` to force PyTorch.

---

## 4. Usage limit and billing alert (do this before heavy testing)

1. Railway dashboard → account switcher → workspace → **Usage**  
   (or [Cost Control](https://docs.railway.com/pricing/cost-control)).
2. **Set Usage Limits**:
   - **Custom email alert (soft):** e.g. `$15` — email only, services keep running.
   - **Hard limit:** e.g. `$25` (minimum hard limit is **$10**) — workloads stop at the cap.
3. Or CLI:

```bash
railway usage limit set --target workspace --soft 15 --hard 25
railway usage limit status
```

Plan: stay on **Hobby**, measure real monthly usage after ~1 week of shop traffic, then
decide whether **Pro** is needed.

---

## 5. Local docker-compose (dev)

```powershell
cd D:\amgold
docker compose up -d
cd backend
copy .env.example .env
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

With R2 unset, files go to `STORAGE_LOCAL_DIR` (`data/storage`).

---

## 6. Backups (follow-up)

- Nightly cron / Railway cron service: `pg_dump` → upload to `R2_BACKUP_BUCKET`.
- Retention 14–30 days; document restore in `docs/RUNBOOK.md` (later phase).
- Do not rely on Railway volume alone as the only copy.

---

## 7. Checklist

- [ ] R2 media (public) + backups (private) + API token  
- [ ] Railway project, region Singapore  
- [ ] pgvector Postgres template + volume  
- [ ] api service, Root Directory `backend`, Serverless **off**  
- [ ] Env vars set; private `DATABASE_URL`  
- [ ] Usage soft alert + hard limit  
- [ ] `alembic upgrade head`  
- [ ] `GET /health` → `{"ok":true}`  
