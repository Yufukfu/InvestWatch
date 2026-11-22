"""What a block looks like: the statuses and challenge-page markers that end a run as `blocked`.

No dependency on the fetch client, so the renderer image can carry this module next to `addresses` (ADR 0107).
"""

BLOCK_STATUSES = frozenset({403, 429})
# Challenge pages are small. A large page that merely embeds a captcha widget (a contact or newsletter
# form) is a real page, and `blocked` would not be retried, so the marker scan skips it.
_MARKER_SCAN_MAX_BYTES = 20_000
# Vendor-specific names found in challenge pages. The bare word "captcha" is not a marker: the real KNF
# page contains it in ordinary text.
_BLOCK_MARKERS = (
    b"g-recaptcha",
    b"h-captcha",
    b"hcaptcha.com",
    b"cf-turnstile",
    b"cf-chl-",
    b"/cdn-cgi/challenge-platform",
    b"captcha-delivery.com",
    b"px-captcha",
)


def block_marker(body: bytes) -> str | None:
    if len(body) > _MARKER_SCAN_MAX_BYTES:
        return None
    lowered = body.lower()
    return next((m.decode() for m in _BLOCK_MARKERS if m in lowered), None)
