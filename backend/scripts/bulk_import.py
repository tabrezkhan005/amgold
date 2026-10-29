"""
Bulk-import a folder tree + CSV into Postgres/R2 (resumable, idempotent by product code).

Expected layout:
  import_root/
    catalog.csv          # code,name,category,price,weight_g,description,difference_note,...
    photos/
      AMG-0001/
        1.jpg
        2.jpg
        ...
      AMG-0002/
        ...

CSV columns (header required): code,name,category,price
Optional: material,weight_g,description,difference_note,hsn_code,gst_rate,unit,similar_to
  (similar_to = semicolon-separated codes)

Usage:
  python scripts/bulk_import.py --root D:\\amgold_import --resume
"""

from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

from app.config import clear_settings_cache, get_settings
from app.db.models import Product
from app.db.session import get_session_factory, reset_engine
from app.ml.embedder import load_embedder
from app.services import catalog as catalog_svc
from app.services.storage import build_storage


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _load_photos(folder: Path) -> list[bytes]:
    files = sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    return [p.read_bytes() for p in files]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--photos-dir", type=Path, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip existing codes")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    root: Path = args.root
    csv_path = args.csv or (root / "catalog.csv")
    photos_dir = args.photos_dir or (root / "photos")
    if not csv_path.is_file():
        print(f"Missing CSV: {csv_path}", file=sys.stderr)
        return 1

    clear_settings_cache()
    settings = get_settings()
    reset_engine()
    SessionLocal = get_session_factory(settings)
    storage = build_storage(settings)
    embedder = load_embedder(settings.model_name, warm_up=True)

    imported = skipped = failed = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if args.limit:
        rows = rows[: args.limit]

    for row in rows:
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        if not code or not name:
            failed += 1
            print(f"SKIP bad row: {row}")
            continue
        photo_folder = photos_dir / code
        if not photo_folder.is_dir():
            failed += 1
            print(f"FAIL {code}: no photo folder {photo_folder}")
            continue
        photos = _load_photos(photo_folder)
        if len(photos) < 3:
            failed += 1
            print(f"FAIL {code}: {len(photos)} photos (need >= 3)")
            continue

        with SessionLocal() as db:
            existing = db.query(Product).filter(Product.code == code).first()
            if existing and args.resume:
                skipped += 1
                print(f"RESUME skip {code}")
                continue
            if existing and not args.resume:
                failed += 1
                print(f"FAIL {code}: already exists (use --resume)")
                continue
            try:
                fields = {
                    "code": code,
                    "name": name,
                    "category": (row.get("category") or "other").strip(),
                    "material": (row.get("material") or "rolled_gold").strip(),
                    "price": Decimal(str(row.get("price") or "0")),
                    "weight_g": Decimal(str(row["weight_g"])) if row.get("weight_g") else None,
                    "description": row.get("description") or None,
                    "difference_note": row.get("difference_note") or None,
                    "hsn_code": row.get("hsn_code") or None,
                    "gst_rate": Decimal(str(row["gst_rate"])) if row.get("gst_rate") else None,
                    "unit": (row.get("unit") or "pcs").strip(),
                }
                product = catalog_svc.create_product_row(db, fields=fields, created_by=None)
                catalog_svc.enroll_photos(
                    db,
                    product=product,
                    photos=photos,
                    embedder=embedder,
                    storage=storage,
                    settings=settings,
                    source="import",
                )
                similar = (row.get("similar_to") or "").strip()
                if similar:
                    for other_code in [c.strip() for c in similar.split(";") if c.strip()]:
                        other = db.query(Product).filter(Product.code == other_code).first()
                        if other:
                            catalog_svc.add_link(db, product.id, other.id, note="import")
                catalog_svc.write_audit(
                    db,
                    actor_type="admin",
                    actor_id="bulk_import",
                    action="import_product",
                    entity="product",
                    entity_id=str(product.id),
                    data={"code": code, "photos": len(photos)},
                )
                db.commit()
                imported += 1
                print(f"OK {code} photos={len(photos)}")
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed += 1
                print(f"FAIL {code}: {exc}")

    print(f"done imported={imported} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
