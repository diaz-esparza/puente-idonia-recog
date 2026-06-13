"""Module that models the PKI procedure, important to audit."""
# pyright: reportMissingTypeStubs=false

import asyncio
import os
from functools import lru_cache
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rfc3161ng import (
    RemoteTimestamper,
    TimestampingError,
    encode_timestamp_response,  # pyright:ignore[reportUnknownVariableType]
)

from puente.config import get_settings
from puente.telemetry.getters import get_logger

_logger = get_logger(__name__)


def to_canonical_bin(x: object) -> bytes:
    """Deterministic canonical binary serialization."""
    return cbor2.dumps(x, canonical=True)


def _save_private_key(
    private_key: Ed25519PrivateKey,
    location: Path,
    password: bytes | None,
) -> None:
    """Saves the private key on disk, with an optional password."""
    encryption_algorythm = (
        serialization.BestAvailableEncryption(
            password=password,
        )
        if password is not None
        else serialization.NoEncryption()
    )
    location.parent.mkdir(parents=True, exist_ok=True)
    with open(location, "wb") as f:
        _ = f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption_algorythm,
            )
        )
    os.chmod(location, 0o600)


def _save_derived_public_key(
    private_key: Ed25519PrivateKey,
    location: Path,
) -> None:
    public_key = private_key.public_key()
    location.parent.mkdir(parents=True, exist_ok=True)
    with open(location, "wb") as f:
        _ = f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    _logger.info("public_key_save")


@lru_cache(maxsize=1)
def keygen() -> Ed25519PrivateKey:
    """Loads the private key from disk, or generates it if not present,
    cached after first use.

    This function also re-generates and overwrites the public key.
    """
    settings = get_settings()
    private_key_file = settings.audit_private_key_file
    private_key_password = settings.audit_private_key_password
    if private_key_file.exists():
        with open(private_key_file, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=private_key_password,
            )
        _logger.info("private_key_load")
        if not isinstance(private_key, Ed25519PrivateKey):
            raise TypeError(
                f"Expected a {Ed25519PrivateKey.__name__} private key, "
                + f"got {private_key.__class__.__name__}."
            )
    else:
        private_key = Ed25519PrivateKey.generate()
        _logger.info("private_key_generate")
        _save_private_key(private_key, private_key_file, private_key_password)
        _logger.info("private_key_save")
    _save_derived_public_key(private_key, settings.audit_public_key_file)
    return private_key


async def timestamp(signature: bytes) -> bytes | None:
    """Requests the configured TSA to time-seal the input signature.

    Logs the excetion and returns 'None' on typical TSA-related errors.

    A few regards:
        - The function uses `asyncio.to_thread` to not block the event
        loop on request (as the library uses the `requests` library).
        Performance improvements are possible through a port to httpx.
        - In real production, more efforts should be done to assure TSA
        availability, like fallback providers and delay/retry logic.
    """
    settings = get_settings()
    try:
        tsa = RemoteTimestamper(
            settings.audit_tsa_url,
            hashname="sha256",
            timeout=10,
        )
        tsr_response = await asyncio.to_thread(  # pyright: ignore[reportUnknownVariableType]
            tsa,
            signature,
            return_tsr=True,
        )
        tsr_bytes = encode_timestamp_response(tsr_response)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        if isinstance(tsr_bytes, bytes):
            _logger.info("timestamp_success")
            return tsr_bytes
        _logger.exception("timestamp_format_error")
    except TimestampingError:
        _logger.exception("timestamp_response_error")
    except Exception:
        _logger.exception("timestamp_unexpected_error")
    return None
