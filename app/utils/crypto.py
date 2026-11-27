"""
EBT System — Cryptographic & Masking Utilities
Provides Fernet symmetric authenticated cryptography (AES-128-CBC with PKCS7 padding
and HMAC-SHA256 authentication using a 256-bit derived key) for sensitive PII
(Aadhaar, PAN, Bank details) and clean masking utilities for UI presentation.
"""

import base64
import hashlib
import os
from cryptography.fernet import Fernet
from flask import current_app


def get_encryption_key() -> bytes:
    """
    Derive a deterministic 32-byte urlsafe base64 key for Fernet.
    Key precedence:
    1. Dedicated ENCRYPTION_KEY environment variable.
    2. Flask config SECRET_KEY or environment variable SECRET_KEY.
    
    In production environments (FLASK_ENV=production or RENDER=true),
    a secure key must be explicitly configured; insecure hardcoded fallbacks
    are strictly rejected.
    """
    # 1. Check dedicated ENCRYPTION_KEY environment variable first
    dedicated = os.environ.get("ENCRYPTION_KEY")
    if dedicated and len(dedicated.strip()) >= 16:
        secret = dedicated.strip()
    else:
        try:
            secret = current_app.config.get("SECRET_KEY")
        except RuntimeError:
            secret = os.environ.get("SECRET_KEY")

        if not secret:
            # Check environment: reject default fallback in production/Render
            is_prod = (
                os.environ.get("FLASK_ENV") == "production"
                or os.environ.get("RENDER") == "true"
                or os.environ.get("ENVIRONMENT") == "production"
            )
            if is_prod:
                raise RuntimeError(
                    "CRITICAL SECURITY ERROR: Neither ENCRYPTION_KEY nor SECRET_KEY is set in production. "
                    "A secure production key is mandatory for PII encryption."
                )
            # Only allowed in local non-production development/testing
            secret = "hrms360-dev-test-only-key-not-for-production"

    # Hash secret to 32 bytes and base64-encode for Fernet (AES-128-CBC + HMAC-SHA256)
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_field(raw_value: str) -> str:
    """Encrypt a sensitive plaintext string into a Fernet token."""
    if not raw_value:
        return ""
    try:
        f = Fernet(get_encryption_key())
        return f.encrypt(raw_value.strip().encode("utf-8")).decode("utf-8")
    except Exception:
        return raw_value


def decrypt_field(encrypted_token: str) -> str:
    """Decrypt a Fernet token back into plaintext. Returns raw token if decryption fails."""
    if not encrypted_token:
        return ""
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(encrypted_token.strip().encode("utf-8")).decode("utf-8")
    except Exception:
        # If not encrypted or using legacy plain text, return as is
        return encrypted_token


def mask_aadhaar(aadhaar: str) -> str:
    """
    Mask Aadhaar number to display only last 4 digits:
    e.g. 123456789012 -> 'XXXX-XXXX-9012'
    """
    if not aadhaar:
        return "—"
    clean = "".join(ch for ch in str(aadhaar) if ch.isalnum())
    if len(clean) >= 4:
        last4 = clean[-4:]
        return f"XXXX-XXXX-{last4}"
    return "XXXX-XXXX-XXXX"


def mask_pan(pan: str) -> str:
    """
    Mask PAN number:
    e.g. ABCDE1234F -> 'ABCXX•••4F'
    """
    if not pan:
        return "—"
    clean = str(pan).strip().upper()
    if len(clean) >= 5:
        first3 = clean[:3]
        last2 = clean[-2:]
        return f"{first3}•••{last2}"
    return "••••••••••"


def mask_bank_account(acc: str) -> str:
    """
    Mask Bank Account number to show only last 4 digits:
    e.g. 1234567890123 -> '••••••••9123'
    """
    if not acc:
        return "—"
    clean = str(acc).strip()
    if len(clean) >= 4:
        return f"••••••••{clean[-4:]}"
    return "••••••••"
