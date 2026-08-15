"""Minimal server-side Google OpenID Connect authorization-code flow."""

from __future__ import annotations

import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from utils.config import settings


def enabled() -> bool:
    cfg = settings()
    return bool(cfg.google_client_id and cfg.google_client_secret)


def new_state() -> str:
    return secrets.token_urlsafe(32)


def _request_host(request) -> str:
    forwarded = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    # Coolify normally sends one host, but RFC 7239-compatible proxies may
    # append a comma-separated chain. Only the original public host matters.
    host = forwarded.split(",", 1)[0].strip().lower()
    return host.split(":", 1)[0]


def callback_uri(request) -> str:
    cfg = settings()
    configured = cfg.google_redirect_uri.strip()
    configured_host = (urlsplit(configured).hostname or "").lower() if configured else ""
    allowed_hosts = {
        item.strip().lower()
        for item in cfg.google_redirect_hosts.split(",")
        if item.strip()
    }
    if configured_host:
        allowed_hosts.add(configured_host)

    host = _request_host(request)
    if host and host in allowed_hosts:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https")
        proto = proto.split(",", 1)[0].strip().lower()
        if proto not in {"http", "https"}:
            proto = "https"
        return f"{proto}://{host}/auth/google/callback"
    if configured:
        return configured
    raise RuntimeError("Google OAuth redirect URI is not configured for this host")


def authorize_url(request, state: str) -> str:
    cfg = settings()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": cfg.google_client_id,
        "redirect_uri": callback_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })


def _json_request(url: str, *, data: dict | None = None, token: str | None = None) -> dict:
    body = urlencode(data).encode() if data else None
    headers = {"Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, data=body, headers=headers), timeout=20) as response:
        value = json.loads(response.read())
    return value if isinstance(value, dict) else {}


def exchange(request, code: str) -> dict[str, str] | None:
    cfg = settings()
    try:
        token = _json_request("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": cfg.google_client_id,
            "client_secret": cfg.google_client_secret,
            "redirect_uri": callback_uri(request),
            "grant_type": "authorization_code",
        })
        access_token = token.get("access_token")
        if not access_token:
            return None
        info = _json_request("https://openidconnect.googleapis.com/v1/userinfo", token=access_token)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
    email = str(info.get("email") or "").strip().lower()
    if not email or info.get("email_verified") is not True:
        return None
    domains = {item.strip().lower() for item in cfg.google_allowed_domains.split(",") if item.strip()}
    emails = {item.strip().lower() for item in cfg.google_allowed_emails.split(",") if item.strip()}
    if domains or emails:
        domain = email.rsplit("@", 1)[-1] if "@" in email else ""
        if email not in emails and domain not in domains:
            return None
    return {"email": email, "name": str(info.get("name") or email)}
