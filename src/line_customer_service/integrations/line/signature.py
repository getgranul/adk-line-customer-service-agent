"""Verify LINE webhook signatures against the unmodified request body."""

import base64
import hashlib
import hmac


def is_valid_line_signature(
    *, body: bytes, signature: str | None, channel_secret: str
) -> bool:
    """Validate a signature without parsing or modifying the webhook body.

    A missing secret is a configuration error. A missing or malformed signature
    is an untrusted request and returns False.
    """
    if not channel_secret:
        raise ValueError("LINE channel secret must not be empty.")

    if signature is None:
        return False

    try:
        received_signature = signature.encode("ascii")
    except UnicodeEncodeError:
        return False

    digest = hmac.new(
        channel_secret.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(digest)
    return hmac.compare_digest(expected_signature, received_signature)
