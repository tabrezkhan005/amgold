# Photo guidelines for AmGold catalog

Use these for phone enrollment and for bulk import of the ~2000 designs.

## Per design

- **5 to 8 photos** ideal (minimum **3**; server warns below 5).
- Varied **angle** (front, back/clasp, 3/4, close-up of distinctive detail).
- Varied **lighting** (shop light + one slightly dimmer); avoid harsh glare.
- **Plain background** (tray, cloth, or neutral surface). No cluttered shelves.
- Fill the frame with the ornament; avoid tiny items in a huge empty scene.
- Hold steady; reject blurry shots (app/server warn on blur / too dark / too bright).
- Same physical piece across photos — do not mix look-alike variants in one folder.

## Look-alikes

Near twins (e.g. 8 beads vs 10 beads) must be **separate product codes**. After import,
link them with `product_links` / the app “link as similar” flow and set a clear
`difference_note` (e.g. `8 beads`).

## Bulk import folder layout

```
import_root/
  catalog.csv
  photos/
    AMG-0001/
      1.jpg
      2.jpg
      ...
    AMG-0002/
      ...
```

`catalog.csv` header:

```text
code,name,category,price,material,weight_g,description,difference_note,similar_to
```

`similar_to` = other codes separated by `;`.

Run:

```powershell
cd D:\amgold\backend
.\.venv\Scripts\Activate.ps1
$env:LOAD_EMBEDDER="true"   # or set load_embedder in .env
python scripts\bulk_import.py --root D:\amgold_import --resume
python scripts\validate_catalog.py
python scripts\evaluate.py
```

## Categories

`necklace` | `chain` | `earring` | `bangle` | `ring` | `pendant` | `other`

Material default: `rolled_gold` (never label as real gold).
