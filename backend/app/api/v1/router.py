"""Aggregate v1 routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, bills, desk, devices, health, products, scan

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(devices.router)
api_router.include_router(auth.router)
api_router.include_router(auth.me_router)
api_router.include_router(admin.router)
api_router.include_router(products.router)
api_router.include_router(scan.router)
api_router.include_router(bills.router)
api_router.include_router(desk.router)

