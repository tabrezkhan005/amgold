"""
Simulate a phone creating bill drafts for desk testing (no Flutter needed).

Requires:
  - running API
  - X-Admin-Key to mint a desk token if --desk-token omitted
  - a staff JWT + device token OR use --admin-as-staff (dev only: uses dependency-free
    path is not available — use enroll/login first)

Simplest path for desk-only testing:
  1) create desk token via admin
  2) create drafts via this script using --access-token and --device-token from a real login
     OR use the temporary --bootstrap helper that creates a user/device via admin APIs.

Usage:
  python scripts/simulate_phone_drafts.py \\
    --base-url http://127.0.0.1:8000 \\
    --admin-key <ADMIN_API_KEY> \\
    --count 2
"""

from __future__ import annotations

import argparse
import sys
import uuid
from decimal import Decimal

import httpx


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--admin-key", required=True)
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--customer", default="Simulated Customer")
    p.add_argument("--phone", default="9999999999")
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    admin = {"X-Admin-Key": args.admin_key}

    with httpx.Client(base_url=base, timeout=30.0) as client:
        # Ensure owner + enrollment + device + login
        uname = f"sim_{uuid.uuid4().hex[:6]}"
        pin = "2468"
        r = client.post(
            "/v1/admin/users",
            headers=admin,
            json={
                "username": uname,
                "display_name": "Simulator",
                "role": "staff",
                "pin": pin,
            },
        )
        if r.status_code not in (200, 409):
            print("create user failed", r.status_code, r.text, file=sys.stderr)
            return 1

        r = client.post(
            "/v1/admin/enrollment-codes",
            headers=admin,
            json={"label": "sim-phone", "expires_hours": 48},
        )
        r.raise_for_status()
        code = r.json()["code"]

        r = client.post(
            "/v1/devices/enroll",
            json={
                "code": code,
                "label": "sim",
                "platform": "android",
                "app_version": "sim",
            },
        )
        if r.status_code == 403 and r.json().get("code") == "max_devices":
            print(
                "max devices reached — revoke one with create_admin_codes.py --revoke-device",
                file=sys.stderr,
            )
            return 1
        r.raise_for_status()
        device_token = r.json()["device_token"]

        r = client.post(
            "/v1/auth/login",
            headers={"X-Device-Token": device_token},
            json={"username": uname, "pin": pin},
        )
        r.raise_for_status()
        access = r.json()["access_token"]
        phone_headers = {
            "Authorization": f"Bearer {access}",
            "X-Device-Token": device_token,
        }

        for i in range(args.count):
            draft_id = str(uuid.uuid4())
            payload = {
                "client_draft_id": draft_id,
                "customer_name": args.customer,
                "customer_phone": args.phone,
                "notes": f"simulated draft {i + 1}",
                "items": [
                    {
                        "product_id": None,
                        "code": "AMG-0001",
                        "name": "PLACEHOLDER Necklace",
                        "unit_price": str(Decimal("450.00")),
                        "quantity": str(Decimal(i + 1)),
                        "unit": "pcs",
                    },
                    {
                        "product_id": None,
                        "code": "AMG-0002",
                        "name": "PLACEHOLDER Chain",
                        "unit_price": "300.00",
                        "quantity": "1",
                        "unit": "pcs",
                    },
                ],
            }
            r = client.post("/v1/bills/drafts", headers=phone_headers, json=payload)
            r.raise_for_status()
            print(f"draft {r.json()['id']} status={r.json()['status']}")

        print("done — open InvGen Mobile Bills (or GET /v1/desk/drafts with desk token)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
