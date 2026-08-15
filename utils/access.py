"""Fail-closed RBAC, record scope, and audited admin role preview."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, replace

from db import execute, fetch_one

ADMIN_EMAIL = "kaljuvee@gmail.com"
ROLES = ("admin", "supplier", "investor", "payer")
PUBLIC_ROLES = ("supplier", "investor", "payer")
ROLE_ALIASES = {"seller": "supplier", "borrower": "supplier"}


@dataclass(frozen=True)
class AccessContext:
    email: str = ""
    name: str = ""
    actual_role: str = "anonymous"
    effective_role: str = "anonymous"
    status: str = "anonymous"
    is_verified: bool = False
    preview: bool = False
    company_id: int | None = None
    investor_user_id: int | None = None
    supplier_user_id: int | None = None
    payer_registration: str = ""
    is_synthetic: bool = False
    csrf_token: str = ""
    session_version: int = 0

    @property
    def authenticated(self) -> bool:
        return bool(self.email and self.status == "active" and self.is_verified)


_CONTEXT: ContextVar[AccessContext] = ContextVar(
    "fastfactoring_access_context", default=AccessContext()
)


def normalize_role(value: str | None) -> str:
    role = ROLE_ALIASES.get((value or "").strip().lower(), (value or "").strip().lower())
    return role if role in ROLES else ""


def _profile(email: str) -> dict | None:
    return fetch_one(
        """SELECT u.email,u.name,u.status,u.is_verified,u.session_version,p.role,p.company_id,
                  p.investor_user_id,p.supplier_user_id,p.payer_registration,p.is_synthetic
             FROM factorio.app_users u
             LEFT JOIN factorio.access_profiles p ON p.email=u.email
            WHERE lower(u.email)=%(email)s""",
        {"email": email},
    )


def _synthetic_scope(role: str) -> dict:
    if role == "supplier":
        row = fetch_one(
            """SELECT u.id supplier_user_id,i.company_id FROM factorio.users u
                 LEFT JOIN LATERAL (
                   SELECT company_id FROM factorio.invoices WHERE seller_id=u.id ORDER BY id LIMIT 1
                 ) i ON TRUE
                WHERE u.email='seller1@factorio.co.uk' AND u.role='seller'"""
        ) or {}
        return {"supplier_user_id": row.get("supplier_user_id"),
                "company_id": row.get("company_id"), "is_synthetic": True}
    if role == "investor":
        row = fetch_one(
            "SELECT id FROM factorio.users WHERE email='investor1@factorio.co.uk' AND role='investor'"
        ) or {}
        return {"investor_user_id": row.get("id"), "is_synthetic": True}
    if role == "payer":
        row = fetch_one(
            """SELECT debtor_registration FROM factorio.invoices
                WHERE debtor_registration<>'' AND is_synthetic=TRUE ORDER BY id LIMIT 1"""
        ) or {}
        return {"payer_registration": row.get("debtor_registration", ""), "is_synthetic": True}
    return {}


def context_for(req) -> AccessContext:
    session = getattr(req, "session", None) or {}
    email = str(session.get("uid") or "").strip().lower()
    if not email:
        ctx = AccessContext()
        _CONTEXT.set(ctx)
        return ctx
    try:
        row = _profile(email)
    except Exception:
        row = None
    if not row:
        ctx = AccessContext(email=email, name=str(session.get("name") or ""), status="pending")
        _CONTEXT.set(ctx)
        return ctx
    stored_role = normalize_role(row.get("role"))
    actual = "admin" if email == ADMIN_EMAIL else ("" if stored_role == "admin" else stored_role)
    if not actual:
        actual = "pending"
    status = str(row.get("status") or "pending")
    stored_version = int(row.get("session_version") or 0)
    session_version = int(session.get("session_version") or 0)
    if not session_version or session_version != stored_version:
        status = "revoked"
    ctx = AccessContext(
        email=email,
        name=str(row.get("name") or session.get("name") or email),
        actual_role=actual,
        effective_role=actual,
        status=status,
        is_verified=bool(row.get("is_verified")),
        company_id=row.get("company_id"),
        investor_user_id=row.get("investor_user_id"),
        supplier_user_id=row.get("supplier_user_id"),
        payer_registration=str(row.get("payer_registration") or ""),
        is_synthetic=bool(row.get("is_synthetic")),
        csrf_token=str(session.get("csrf_token") or ""),
        session_version=stored_version,
    )
    requested = normalize_role(session.get("preview_role"))
    if actual == "admin" and requested and requested != "admin":
        try:
            scope = _synthetic_scope(requested)
        except Exception:
            scope = {}
        ctx = replace(
            ctx,
            effective_role=requested,
            preview=True,
            company_id=scope.get("company_id"),
            investor_user_id=scope.get("investor_user_id"),
            supplier_user_id=scope.get("supplier_user_id"),
            payer_registration=scope.get("payer_registration", ""),
            is_synthetic=bool(scope.get("is_synthetic")),
        )
    _CONTEXT.set(ctx)
    return ctx


def current_context() -> AccessContext:
    return _CONTEXT.get()


_ROLE_PREFIXES = {
    "supplier": ("/app/supplier", "/app/seller"),
    "investor": (
        "/app/dashboard", "/app/marketplace", "/app/portfolio", "/app/statement",
        "/app/auto-invest", "/app/triage", "/app/assistant",
    ),
    "payer": ("/app/payer",),
}
_COMMON_PREFIXES = (
    "/app/chat", "/app/copilot", "/app/role-preview", "/app/preview-exit",
    "/app/invoice-pdf",
)


def path_allowed(ctx: AccessContext, path: str) -> bool:
    """Authorize an app route before its handler runs; handlers still scope records."""
    if not ctx.authenticated or ctx.effective_role not in ROLES:
        return False
    if path == "/app" or path.startswith(_COMMON_PREFIXES):
        return True
    if ctx.effective_role == "admin":
        return True
    return path.startswith(_ROLE_PREFIXES.get(ctx.effective_role, ()))


def audit(ctx: AccessContext, action: str, entity: str = "", detail: str = "") -> None:
    try:
        execute(
            """INSERT INTO factorio.audit_log(actor,role,action,entity,detail)
               VALUES (%(actor)s,%(role)s,%(action)s,%(entity)s,%(detail)s)""",
            {
                "actor": ctx.email or "anonymous",
                "role": ctx.effective_role,
                "action": action,
                "entity": entity,
                "detail": detail,
            },
        )
    except Exception:
        pass


def preview_side_effect_allowed(ctx: AccessContext) -> bool:
    """Role preview may mutate only the checked-in/synthetic scenario corpus."""
    return not ctx.preview or ctx.is_synthetic


_PREVIEW_WRITE_PATHS = {
    "/app/supplier/extract", "/app/supplier/details", "/app/supplier/change",
    "/app/supplier/accept", "/app/payer/invoice-action", "/app/chat/share",
    "/app/marketplace/invest",
}


def preview_request_allowed(ctx: AccessContext, path: str, method: str) -> bool:
    """Keep preview writes inside the explicitly scoped synthetic scenarios."""
    if not ctx.preview:
        return True
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return path not in {"/app/marketplace/secondary/buy", "/app/admin/integrations/toggle"}
    return path in _PREVIEW_WRITE_PATHS and ctx.is_synthetic
