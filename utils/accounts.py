"""PostgreSQL-backed identities, registration, invitations, and reset tokens."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psycopg.rows import dict_row

from db import connect, fetch_all, fetch_one
from utils.access import ADMIN_EMAIL, PUBLIC_ROLES, normalize_role
from utils.config import settings


def valid_email(value: str | None) -> str:
    email = (value or "").strip().lower()
    return email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) else ""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        marker, cost, raw_salt, raw_digest = encoded.split("$", 3)
        if marker != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(raw_salt)
        expected = base64.urlsafe_b64decode(raw_digest)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=int(cost), r=8, p=1)
        return secrets.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _rate_allowed(subject: str, action: str, limit: int, window_seconds: int) -> bool:
    now = datetime.now(timezone.utc)
    digest = token_hash(subject or "anonymous")
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT window_start,attempts FROM factorio.auth_limits "
                "WHERE subject_hash=%s AND action=%s FOR UPDATE",
                (digest, action),
            )
            row = cur.fetchone()
            if not row or row["window_start"] <= now - timedelta(seconds=window_seconds):
                cur.execute(
                    """INSERT INTO factorio.auth_limits(subject_hash,action,window_start,attempts)
                       VALUES (%s,%s,%s,1)
                       ON CONFLICT(subject_hash,action) DO UPDATE
                       SET window_start=EXCLUDED.window_start,attempts=1""",
                    (digest, action, now),
                )
                allowed = True
            elif row["attempts"] >= limit:
                allowed = False
            else:
                cur.execute(
                    "UPDATE factorio.auth_limits SET attempts=attempts+1 "
                    "WHERE subject_hash=%s AND action=%s",
                    (digest, action),
                )
                allowed = True
        conn.commit()
    return allowed


def _issue_token(cur, email: str, purpose: str, ttl_seconds: int) -> str:
    cur.execute(
        "UPDATE factorio.auth_tokens SET used_at=now() "
        "WHERE email=%s AND purpose=%s AND used_at IS NULL",
        (email, purpose),
    )
    token = secrets.token_urlsafe(32)
    cur.execute(
        """INSERT INTO factorio.auth_tokens(email,purpose,token_hash,expires_at)
           VALUES (%s,%s,%s,now()+(%s * interval '1 second'))""",
        (email, purpose, token_hash(token), ttl_seconds),
    )
    return token


def _ensure_subject(cur, email: str, name: str, role: str) -> dict:
    result = {"supplier_user_id": None, "investor_user_id": None}
    if role not in {"supplier", "investor"}:
        return result
    legacy_role = "seller" if role == "supplier" else "investor"
    cur.execute(
        """INSERT INTO factorio.users(email,username,role,is_verified)
           VALUES (%s,%s,%s,TRUE)
           ON CONFLICT(email) DO UPDATE SET username=EXCLUDED.username,
               role=EXCLUDED.role,is_verified=TRUE
           RETURNING id""",
        (email, name or email.split("@", 1)[0], legacy_role),
    )
    returned = cur.fetchone()
    user_id = returned["id"] if isinstance(returned, dict) else returned[0]
    result["supplier_user_id" if role == "supplier" else "investor_user_id"] = user_id
    return result


def _upsert_profile(cur, email: str, name: str, role: str, *, synthetic: bool = False) -> None:
    scope = _ensure_subject(cur, email, name, role)
    cur.execute(
        """INSERT INTO factorio.access_profiles(
               email,role,supplier_user_id,investor_user_id,is_synthetic)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT(email) DO UPDATE SET role=EXCLUDED.role,
               supplier_user_id=EXCLUDED.supplier_user_id,
               investor_user_id=EXCLUDED.investor_user_id,
               company_id=CASE WHEN EXCLUDED.role='supplier' THEN access_profiles.company_id ELSE NULL END,
               payer_registration=CASE WHEN EXCLUDED.role='payer' THEN access_profiles.payer_registration ELSE '' END,
               is_synthetic=access_profiles.is_synthetic OR EXCLUDED.is_synthetic,
               updated_at=now()""",
        (email, role, scope["supplier_user_id"], scope["investor_user_id"], synthetic),
    )


def invite_role(token: str, email: str = "") -> str:
    if not token:
        return ""
    sql = """SELECT role FROM factorio.team_invitations
              WHERE token_hash=%(hash)s AND status='pending' AND expires_at>now()"""
    params = {"hash": token_hash(token)}
    if email:
        sql += " AND lower(email)=%(email)s"
        params["email"] = valid_email(email)
    row = fetch_one(sql, params)
    return normalize_role((row or {}).get("role"))


def register(email: str, password: str, name: str, role: str, invite_token: str = "") -> tuple[bool, str]:
    email, name = valid_email(email), (name or "").strip()[:120]
    invited_role = invite_role(invite_token, email) if invite_token else ""
    if invite_token and not invited_role:
        return False, "This invitation is invalid, expired, or belongs to another email address."
    role = invited_role or normalize_role(role)
    if not email or email == ADMIN_EMAIL or role not in PUBLIC_ROLES or len(password or "") < 10:
        return False, "Use a valid email, a non-admin role, and a password of at least 10 characters."
    if not _rate_allowed(email, "register", 5, 3600):
        return False, "Too many attempts. Please try again later."
    encoded = hash_password(password)
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT is_verified FROM factorio.app_users WHERE email=%s FOR UPDATE", (email,))
            existing = cur.fetchone()
            if existing and existing["is_verified"]:
                conn.commit()
                return True, "If this address can be registered, a verification email is on its way."
            cur.execute(
                """INSERT INTO factorio.app_users(
                       email,name,salt,pw_hash,role,subrole,is_verified,status,updated_at)
                   VALUES (%s,%s,'',%s,%s,'ops',FALSE,'pending',now())
                   ON CONFLICT(email) DO UPDATE SET name=EXCLUDED.name,pw_hash=EXCLUDED.pw_hash,
                       role=EXCLUDED.role,status='pending',updated_at=now()""",
                (email, name, encoded, role),
            )
            _upsert_profile(cur, email, name, role)
            token = _issue_token(cur, email, "verify", 24 * 3600)
            if invite_token:
                cur.execute(
                    "UPDATE factorio.team_invitations SET status='accepted',accepted_at=now() "
                    "WHERE token_hash=%s AND lower(email)=%s AND status='pending'",
                    (token_hash(invite_token), email),
                )
        conn.commit()
    delivered = _send_action(email, name, "Verify your Factorio account", "verify", token)
    return True, ("Check your email to verify your account." if delivered else
                  "Account created, but verification email delivery is unavailable. Contact support.")


def authenticate(email: str, password: str) -> dict | None:
    email = valid_email(email)
    if not email or not _rate_allowed(email, "login", 10, 900):
        return None
    row = fetch_one(
        """SELECT email,name,pw_hash,status,is_verified,session_version FROM factorio.app_users
            WHERE email=%(email)s""",
        {"email": email},
    )
    if not row or row["status"] != "active" or not row["is_verified"]:
        return None
    return row if verify_password(password or "", row.get("pw_hash") or "") else None


def verify_account(token: str) -> dict | None:
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """UPDATE factorio.auth_tokens SET used_at=now()
                    WHERE token_hash=%s AND purpose='verify' AND used_at IS NULL
                      AND expires_at>now() RETURNING email""",
                (token_hash(token),),
            )
            used = cur.fetchone()
            if not used:
                conn.rollback()
                return None
            cur.execute(
                "UPDATE factorio.app_users SET is_verified=TRUE,status='active',session_version=session_version+1,updated_at=now() "
                "WHERE email=%s RETURNING email,name,session_version",
                (used["email"],),
            )
            account = cur.fetchone()
        conn.commit()
    return dict(account) if account else None


def forgot(email: str) -> None:
    email = valid_email(email)
    if not email or not _rate_allowed(email, "forgot", 5, 3600):
        return
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT email,name FROM factorio.app_users "
                "WHERE email=%s AND is_verified=TRUE AND status='active' FOR UPDATE",
                (email,),
            )
            account = cur.fetchone()
            if not account:
                conn.commit()
                return
            token = _issue_token(cur, email, "reset", 3600)
        conn.commit()
    _send_action(email, account["name"], "Reset your Factorio password", "reset", token)


def reset_password(token: str, password: str) -> bool:
    if len(password or "") < 10:
        return False
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """UPDATE factorio.auth_tokens SET used_at=now()
                    WHERE token_hash=%s AND purpose='reset' AND used_at IS NULL
                      AND expires_at>now() RETURNING email""",
                (token_hash(token),),
            )
            used = cur.fetchone()
            if not used:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE factorio.app_users SET salt='',pw_hash=%s,session_version=session_version+1,updated_at=now() WHERE email=%s",
                (hash_password(password), used["email"]),
            )
        conn.commit()
    return True


def google_account(email: str, name: str) -> dict | None:
    email, name = valid_email(email), (name or "").strip()[:120]
    if not email:
        return None
    role = "admin" if email == ADMIN_EMAIL else ""
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT email FROM factorio.app_users WHERE email=%s", (email,))
            exists = cur.fetchone()
            cur.execute(
                """INSERT INTO factorio.app_users(
                       email,name,salt,pw_hash,role,subrole,is_verified,google_linked,status,updated_at)
                   VALUES (%s,%s,'','','investor','ops',TRUE,TRUE,%s,now())
                   ON CONFLICT(email) DO UPDATE SET google_linked=TRUE,is_verified=TRUE,
                       name=CASE WHEN factorio.app_users.name='' THEN EXCLUDED.name ELSE factorio.app_users.name END,
                       updated_at=now()""",
                (email, name, "active" if role else "pending"),
            )
            if role:
                _upsert_profile(cur, email, name, role)
            cur.execute(
                """SELECT u.email,u.name,u.status,u.session_version,p.role FROM factorio.app_users u
                   LEFT JOIN factorio.access_profiles p ON p.email=u.email WHERE u.email=%s""",
                (email,),
            )
            account = cur.fetchone()
        conn.commit()
    return {**dict(account), "is_new": not bool(exists)} if account else None


def choose_role(email: str, role: str) -> bool:
    """Finish first-time Google onboarding; active accounts cannot self-switch."""
    email, role = valid_email(email), normalize_role(role)
    if not email or email == ADMIN_EMAIL or role not in PUBLIC_ROLES:
        return False
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT name FROM factorio.app_users
                            WHERE email=%s AND status='pending' AND google_linked=TRUE FOR UPDATE""", (email,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return False
            _upsert_profile(cur, email, row["name"], role)
            cur.execute(
                """UPDATE factorio.app_users SET role=%s,status='active',is_verified=TRUE,
                       session_version=session_version+1,updated_at=now()
                     WHERE email=%s""",
                (role, email),
            )
        conn.commit()
    return True


def demo_account(email: str, name: str, role: str) -> dict | None:
    """Create or refresh one fixed synthetic persona for Factorio host demos."""
    email, role = valid_email(email), normalize_role(role)
    if not email or role not in PUBLIC_ROLES:
        return None
    google_account(email, name)
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _upsert_profile(cur, email, name, role, synthetic=True)
            if role == "supplier":
                cur.execute("""UPDATE factorio.access_profiles p SET company_id=(
                                  SELECT company_id FROM factorio.invoices
                                  WHERE seller_id=p.supplier_user_id AND is_synthetic=TRUE
                                  ORDER BY id LIMIT 1)
                               WHERE email=%s""", (email,))
            elif role == "payer":
                cur.execute("""UPDATE factorio.access_profiles SET payer_registration=(
                                  SELECT debtor_registration FROM factorio.invoices
                                  WHERE is_synthetic=TRUE AND debtor_registration<>'' ORDER BY id LIMIT 1)
                               WHERE email=%s""", (email,))
            cur.execute("""UPDATE factorio.app_users SET role=%s,status='active',is_verified=TRUE,
                              session_version=session_version+1,updated_at=now()
                            WHERE email=%s RETURNING email,name,session_version""", (role, email))
            account = cur.fetchone()
        conn.commit()
    return dict(account) if account else None


def create_invitation(email: str, role: str, actor: str) -> tuple[bool, str]:
    email, role = valid_email(email), normalize_role(role)
    if not email or email == ADMIN_EMAIL or role not in PUBLIC_ROLES:
        return False, "Enter a valid email and non-admin role."
    token = secrets.token_urlsafe(32)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE factorio.team_invitations SET status='revoked' "
                "WHERE lower(email)=%s AND status='pending'",
                (email,),
            )
            cur.execute(
                """INSERT INTO factorio.team_invitations(
                       email,role,invited_by,token_hash,expires_at)
                   VALUES (%s,%s,%s,%s,now()+interval '7 days')""",
                (email, role, actor, token_hash(token)),
            )
        conn.commit()
    delivered = _send_action(email, email.split("@", 1)[0], "Join the Factorio team", "invite", token)
    return True, ("Invitation created and email queued." if delivered else
                  "Invitation created, but email delivery is unavailable. Share it after mail is restored.")


def team_rows() -> list[dict]:
    return fetch_all(
        """SELECT u.email,u.name,u.status,u.is_verified,u.google_linked,p.role,p.is_synthetic,
                  p.payer_registration,
                  u.created_at,u.updated_at
             FROM factorio.app_users u LEFT JOIN factorio.access_profiles p ON p.email=u.email
            ORDER BY CASE WHEN p.role='admin' THEN 0 ELSE 1 END,p.role,u.email"""
    )


def invitation_rows() -> list[dict]:
    return fetch_all(
        """SELECT email,role,status,invited_by,expires_at,created_at
             FROM factorio.team_invitations ORDER BY created_at DESC LIMIT 50"""
    )


def update_member_role(email: str, role: str, payer_registration: str = "") -> bool:
    email, role = valid_email(email), normalize_role(role)
    if not email or email == ADMIN_EMAIL or role not in PUBLIC_ROLES:
        return False
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT name FROM factorio.app_users WHERE email=%s FOR UPDATE", (email,))
            account = cur.fetchone()
            if not account:
                conn.rollback()
                return False
            _upsert_profile(cur, email, account["name"], role)
            cur.execute("UPDATE factorio.app_users SET role=%s,session_version=session_version+1,updated_at=now() WHERE email=%s",
                        (role, email))
            if role == "payer":
                cur.execute("UPDATE factorio.access_profiles SET payer_registration=%s WHERE email=%s",
                            (payer_registration.strip()[:80], email))
        conn.commit()
    return True


def _send_action(email: str, name: str, subject: str, action: str, token: str) -> bool:
    cfg = settings()
    path = "register" if action == "invite" else f"auth/local/{action}"
    query = f"?invite={token}" if action == "invite" else f"/{token}"
    link = f"{cfg.public_url.rstrip('/')}/{path}{query}"
    safe_name, safe_link = html.escape(name or "there"), html.escape(link, quote=True)
    body = (
        f"<p>Hello {safe_name},</p><p><a href=\"{safe_link}\">{html.escape(subject)}</a></p>"
        "<p>This single-use link expires automatically.</p>"
    )
    return _send_email(email, subject, body)


def _send_email(to: str, subject: str, html_body: str) -> bool:
    cfg = settings()
    if not cfg.postmark_api_token or not cfg.from_email:
        return False
    payload = json.dumps({
        "From": cfg.from_email,
        "To": to,
        "Subject": subject,
        "HtmlBody": html_body,
        "TextBody": re.sub(r"<[^>]+>", "", html_body),
        "MessageStream": "outbound",
    }).encode()
    request = Request(
        "https://api.postmarkapp.com/email",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Postmark-Server-Token": cfg.postmark_api_token,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status == 200
    except (HTTPError, URLError, TimeoutError):
        return False
