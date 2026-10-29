# AmGold demo script (prototype)

Audience: supplier owner / staff. Time: ~5–8 minutes.

## Before you start

- Laptop Wi-Fi on; API running on port 8000; phone on the **same Wi-Fi**.
- Index built (`build_index.py`) with real photos for at least P001–P010.
- App launched with correct `--dart-define=API_BASE_URL` and `API_KEY`.
- Login: **staff** / **amgold**.

## What to say and show

1. **Login** — “Staff app, not public. Demo credentials for now.”
2. **Scan a clear design** (e.g. P003 chain or P004 earrings)  
   - Hold piece in frame, good light, tap capture.  
   - “Backend embeds the photo and finds nearest catalog designs — not a trained classifier.”
3. **Results → Detail** — tap the top card, show price, **Rolled gold** label, weight.  
   - “We never call this real gold.”
4. **Look-alike pair** — scan **P001 (10 beads)** or **P002 (8 beads)**.  
   - Expect **ambiguous** banner: “Several close matches…”  
   - Open **Compare** — side-by-side with difference text.  
   - “App never auto-picks when designs are close; staff confirm.”
5. **Add to bill** — qty 2, snackbar, open bill badge.  
6. **Bill / PDF** — customer name, small discount, **Generate PDF & share**.  
   - Point at **₹** and invoice `AMG-YYYYMMDD-NNN`.  
7. **History** — show saved bill.  
8. **Manual search** — type `P00` if a scan fails; “always have a fallback.”

## If something goes wrong

| Problem | What to do / say |
|--------|-------------------|
| “Cannot connect…” | Same Wi-Fi? Laptop IP correct? Firewall port 8000? Restart uvicorn with `--host 0.0.0.0`. |
| 503 / index not ready | Run `build_index.py`, restart API. |
| 401 Unauthorized | `API_KEY` in app dart-define must match `.env`. |
| Low confidence / wrong match | Better lighting, fill the gold frame, retake; or search manually. |
| Ambiguous not showing | Confirm P001/P002 photos exist and `similar_to` is set; margin is close. |
| Camera denied | Settings → Apps → AmGold → Camera → Allow; return to app. |
| Blank product images | Photos missing under `reference_photos/<id>/` or API not reachable for `/photos`. |

## Order of pieces to scan (suggested)

1. Distinct piece (clear match) — confidence  
2. 10-bead necklace (P001) — ambiguous + compare  
3. Optional: retake in worse light — show Retake / Search manually  

## Closing line

“Prototype on 10 designs. Next: more photos, tuned thresholds from `evaluate.py`, then production hardening.”
