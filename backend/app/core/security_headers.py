"""Security headers middleware.

Adds OWASP-recommended security headers to all responses.
"""

from fastapi import Request, Response


async def security_headers_middleware(request: Request, call_next) -> Response:
    response: Response = await call_next(request)

    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # XSS protection (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Only send referrer for same-origin
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Prevent exposing server info
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    # Content Security Policy (API server)
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

    # HSTS — enforce HTTPS (only effective when behind TLS)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Remove server header if present
    if "server" in response.headers:
        del response.headers["server"]

    return response
