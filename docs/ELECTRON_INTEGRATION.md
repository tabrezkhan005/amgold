# Electron / InvGen Integration

Target desk app: **InvGen** at `D:\invgen` (productName **AMGOLD**, Electron + Next.js + better-sqlite3).

AmGold cloud (**Railway**) holds bill **drafts**. InvGen **polls** them, maps to local products/customers, opens the billing UI for confirmation, then acks. Phone and desk can share shop Wi‑Fi; traffic is still **phone → Railway → desk**, not phone → desk LAN.

## Decisions (locked)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Desk flow | Operator **confirms** in InvGen billing UI. Setting `amgold_auto_import` default **OFF**. **Never auto-print.** |
| 2 | Price mismatch | Default line price = **draft** (phone quote). Confirm screen shows a **badge** when InvGen catalog price differs; operator can switch per line. **Never** overwrite InvGen product prices. Missing SKU → custom line + offer **Create product in InvGen**. |
| 3 | Desk sync v1 | **Polling only** (~3 s). Exponential backoff when backend unreachable; status indicator in InvGen settings. **No SSE in v1.** Keep API shaped so `GET /v1/desk/drafts/stream` can be added later. |
| 4 | HSN/GST | **Ignore for v1.** Draft may still carry optional `hsn_code` / `gst_rate`; InvGen uses its own invoice `tax_rate`. **Do not** change InvGen schema. |

## InvGen audit summary

| Area | Location | Notes |
|------|----------|--------|
| Entry | `electron/main.js` | Window, IPC, print, settings |
| DB | `electron/db.js` | better-sqlite3; products, customers, invoices, settings |
| Preload | `electron/preload.js` | `window.electronAPI` bridge |
| Types | `types/electron.d.ts` | IPC typings |
| Billing UI | `app/billing/page.tsx` | Cart → `createInvoice` |
| Products | `app/products/page.tsx` | SKU/code/price/unit/`bill_name` |
| Local drafts | `lib/bill-draft.ts`, `lib/pending-bill-items.ts` | Reuse pattern for cloud → billing cart |
| Print | `printInvoice()` in `main.js` | Thermal or A4; only after operator prints |
| Settings | SQLite `settings` + IPC get/set | Includes `tax_rate`, `printer_type` |

**Implemented on InvGen branch `feature/amgold-connector`:** `electron/amgold-connector/` (poll + mapper + IPC), Settings → AmGold tab, `/mobile-bills` inbox, billing prefill + ack. Feature-flagged (`amgold_enabled` default off).

## Product master mapping

| AmGold draft field | InvGen target | Rule |
|--------------------|---------------|------|
| `code` | `products.sku` or `products.code` | Lookup: prefer exact `sku`, else `code` |
| `name` | `item_name` | Prefer `bill_name` if product found; else draft `name` |
| `quantity` | `qty` | Number |
| `unit_price` | `price` (line) | **Default = draft price.** If InvGen has a different catalog price, badge the line; operator may switch to catalog price for that line only |
| `unit` | `unit` | Default `"Piece"` / InvGen default if missing |
| cloud `product_id` | — | Cloud UUID ≠ InvGen id. After SKU match set local `product_id` |
| `hsn_code` / `gst_rate` | — | Ignored in v1; InvGen invoice `tax_rate` applies |

Unmatched SKU: add as custom line (`product_id: null`) and offer **Create product in InvGen** (pre-fill sku/name/price from draft). Never block billing.

## Customer mapping

- Optional draft `customer_name` / `customer_phone`.
- Resolve: find by phone → else create → use `customer_id` on invoice.
- If absent: match current InvGen walk-in / prompt UX.

## Confirm vs auto-import

1. **Confirm (default):** connector pushes draft into billing UI (same path as `queuePendingBillItems`). Operator edits, saves, prints with existing flow, then ack `imported` + local invoice ref (or `failed` + reason).
2. **Auto-import (setting ON):** create local invoice draft / pre-fill cart automatically — still **no auto-print**. Operator must print explicitly.

## Printing

- Only via existing InvGen print after operator action.
- After successful import ack: `status: "imported"`, `invoice_ref`.
- On cancel/reject: ack `failed` with reason.

## Settings storage for connector

| Key | Purpose |
|-----|---------|
| `amgold_enabled` | Feature flag |
| `amgold_api_base` | Railway HTTPS URL |
| `amgold_desk_token` | Desk token (secret) |
| `amgold_poll_ms` | Default `3000` |
| `amgold_auto_import` | Default `"false"` |
| `amgold_connection_status` | UI: connected / backoff / error |

## Connector module layout (to add in InvGen)

```
electron/amgold-connector/
  index.js          # start/stop; read settings
  client.js         # HTTPS poll pending + ack (no SSE in v1)
  mapper.js         # draft → bill lines + price-diff badges
  bridge.js         # IPC → renderer: amgold-draft-received
```

Poll loop: every ~3 s when healthy; on network/5xx use exponential backoff (e.g. 3s → 6s → 12s → … cap ~60s), reset on success. Surface status in settings.

## IPC additions (proposed)

| Channel | Direction | Role |
|---------|-----------|------|
| `amgold-get-status` | invoke | `{ enabled, connected, lastError, pendingCount, backoffMs }` |
| `amgold-set-config` | invoke | Update settings keys above |
| `amgold-ack` | invoke | `{ draftId, status, invoiceId? }` → POST Railway |
| `amgold-draft` | event | Push draft JSON to renderer |
| `amgold-create-product` | invoke | Optional helper for missing SKU |

## Security

- Desk token only on desk machine; phone JWT cannot ack.
- TLS to Railway only; no open local HTTP port for AmGold.
- Same Wi‑Fi does not relax auth.
- Validate draft belongs to this shop/deployment before showing cart.

## API shape (desk)

- **v1 implemented:** `GET /v1/desk/drafts?status=pending`, `POST /v1/desk/drafts/{id}/ack`
- **Reserved for later:** `GET /v1/desk/drafts/stream` (SSE) — document in API contract but do not ship client support in v1
