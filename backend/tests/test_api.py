"""API auth and /scan tests."""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def test_health_ok(api_client):
    res = api_client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body == {"ok": True}


def test_products_requires_api_key(api_client):
    res = api_client.get("/products")
    assert res.status_code == 401


def test_products_with_key(api_client):
    res = api_client.get("/products", headers={"X-API-Key": "test-key"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_scan_requires_api_key(api_client):
    buf = BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(buf, format="JPEG")
    buf.seek(0)
    res = api_client.post(
        "/scan",
        files={"image": ("q.jpg", buf, "image/jpeg")},
    )
    assert res.status_code == 401


def test_scan_with_generated_image(api_client):
    buf = BytesIO()
    Image.new("RGB", (80, 60), (200, 150, 50)).save(buf, format="JPEG")
    buf.seek(0)
    res = api_client.post(
        "/scan",
        headers={"X-API-Key": "test-key"},
        files={"image": ("query.jpg", buf, "image/jpeg")},
    )
    assert res.status_code == 200
    body = res.json()
    assert "scan_id" in body
    assert body["matches"]
    assert body["matches"][0]["product_id"] == "P001"
    assert "ambiguous" in body
    assert "low_confidence" in body
    # Look-alike P002 should appear via injection or visual ranking
    ids = {m["product_id"] for m in body["matches"]}
    assert "P002" in ids


def test_scan_rejects_non_image(api_client):
    res = api_client.post(
        "/scan",
        headers={"X-API-Key": "test-key"},
        files={"image": ("x.txt", b"not-an-image", "text/plain")},
    )
    assert res.status_code == 400
