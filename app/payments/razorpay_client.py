"""Razorpay SDK client (TEST or LIVE keys via env — no code changes required)."""

from __future__ import annotations

import razorpay

from app.core.config import settings


def get_razorpay_client() -> razorpay.Client:
    key_id = (settings.RAZORPAY_KEY_ID or "").strip()
    key_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay is not configured (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET).")
    return razorpay.Client(auth=(key_id, key_secret))
