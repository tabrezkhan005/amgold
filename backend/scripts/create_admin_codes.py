"""
Provision owner/staff users and enrollment codes (developer tool).

Examples:
  python scripts/create_admin_codes.py --owner owner --owner-pin 1234 \\
      --staff staff --staff-pin 5678 --codes 3 --code-label "Shop phone"

  python scripts/create_admin_codes.py --revoke-device <uuid>
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from app.config import clear_settings_cache, get_settings
from app.db.session import get_session_factory, reset_engine
from app.services import auth_users as auth_svc
from app.services import devices as devices_svc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=None, help="Owner username to create")
    parser.add_argument("--owner-pin", default=None)
    parser.add_argument("--owner-name", default="Owner")
    parser.add_argument("--staff", default=None, help="Staff username to create")
    parser.add_argument("--staff-pin", default=None)
    parser.add_argument("--staff-name", default="Staff")
    parser.add_argument("--codes", type=int, default=0, help="Number of enrollment codes")
    parser.add_argument("--code-label", default="Phone")
    parser.add_argument("--expires-hours", type=int, default=48)
    parser.add_argument("--revoke-device", default=None, help="Device UUID to revoke")
    parser.add_argument("--desk-label", default=None, help="Create desk client with this label")
    args = parser.parse_args()

    clear_settings_cache()
    settings = get_settings()
    reset_engine()
    SessionLocal = get_session_factory(settings)

    with SessionLocal() as db:
        if args.revoke_device:
            device = devices_svc.revoke_device(db, UUID(args.revoke_device))
            db.commit()
            print(f"revoked device {device.id} label={device.label}")
            return 0

        if args.owner:
            if not args.owner_pin:
                print("--owner-pin required", file=sys.stderr)
                return 1
            user = auth_svc.create_user(
                db,
                username=args.owner,
                display_name=args.owner_name,
                role="owner",
                pin=args.owner_pin,
            )
            db.commit()
            print(f"owner id={user.id} username={user.username}")

        if args.staff:
            if not args.staff_pin:
                print("--staff-pin required", file=sys.stderr)
                return 1
            user = auth_svc.create_user(
                db,
                username=args.staff,
                display_name=args.staff_name,
                role="staff",
                pin=args.staff_pin,
            )
            db.commit()
            print(f"staff id={user.id} username={user.username}")

        for i in range(args.codes):
            label = f"{args.code_label} {i + 1}" if args.codes > 1 else args.code_label
            row, raw = devices_svc.create_enrollment_code(
                db, label=label, expires_hours=args.expires_hours
            )
            db.commit()
            print(f"enrollment_code id={row.id} label={row.label} code={raw} expires={row.expires_at.isoformat()}")

        if args.desk_label:
            client, token = auth_svc.create_desk_client(db, label=args.desk_label)
            db.commit()
            print(f"desk_client id={client.id} label={client.label} token={token}")
            print("(store the desk token now — it is not shown again)")

    print("done")
    print(f"admin API key is whatever you set as ADMIN_API_KEY (never printed).")
    print(f"max_devices={settings.max_devices}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
