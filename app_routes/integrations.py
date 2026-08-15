"""Integrations layer — production module (step 9).

A registry of external connectors (accounting, open banking, credit bureau,
e-signature, collections, e-invoice) with connect/disconnect (SoD-scoped to
Executive/Super) and a **working inbound webhook** that ingests an invoice via
JSON — a real integration surface, not just a settings page.
"""

from __future__ import annotations

from fasthtml.common import Div, P, Span, A, H3, NotStr, Form, Input, Button
from starlette.responses import RedirectResponse, JSONResponse

from app import rt
from utils.i18n import get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, current_role, current_subrole
from app_routes.admin import log_action

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

CAN_CONFIG = {"exec", "super"}

CONNECTORS = [
    ("QuickBooks", "accounting", "Sync invoices & GL from QuickBooks Online", True),
    ("Xero", "accounting", "Pull invoices and contacts from Xero", False),
    ("1C", "accounting", "Import from 1C (CIS accounting standard)", False),
    ("Open Banking", "banking", "Bank-account cash-flow feed for scoring & reconciliation", True),
    ("CRIF bureau", "bureau", "Debtor credit reports & scores", True),
    ("SignWise", "esign", "Legally-binding e-signatures for assignments", False),
    ("Creditreform", "collections", "Automated overdue-debt collections handoff", False),
    ("E-Invoice Network", "einvoice", "Government e-invoice verification & buyer confirmation", True),
]


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.integrations (
        name TEXT PRIMARY KEY, kind TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
        connected BOOLEAN NOT NULL DEFAULT FALSE, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def seed_integrations() -> int:
    _ensure()
    if not _HAS_DB:
        return 0
    n = 0
    for name, kind, desc, conn in CONNECTORS:
        if fetch_one("SELECT 1 FROM factorio.integrations WHERE name=%(n)s", {"n": name}):
            continue
        execute("INSERT INTO factorio.integrations (name,kind,description,connected) VALUES (%(n)s,%(k)s,%(d)s,%(c)s)",
                {"n": name, "k": kind, "d": desc, "c": conn})
        n += 1
    return n


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


_KIND_ICON = {"accounting": "\U0001F4D8", "banking": "\U0001F3E6", "bureau": "\U0001F4CA",
              "esign": "✍️", "collections": "\U0001F4E9", "einvoice": "\U0001F9FE"}


@rt("/app/admin/integrations")
def integrations(req):
    g = _guard(req)
    if g:
        return g
    try:
        seed_integrations()
    except Exception:
        pass
    can = current_subrole(req) in CAN_CONFIG
    data = fetch_all("SELECT name,kind,description,connected FROM factorio.integrations ORDER BY connected DESC, kind") if _HAS_DB else []
    cards = []
    for r in data:
        conn = r["connected"]
        action = Span("—", cls="text-ink-dim text-xs")
        if can:
            from utils.access import context_for
            action = Form(
                Input(type="hidden", name="name", value=r["name"]),
                Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
                Button("Disconnect" if conn else "Connect", type="submit",
                       cls=("text-xs px-3 py-1 rounded-full " + ("border border-line text-ink" if conn
                            else "bg-accent text-bg"))),
                method="post", action="/app/admin/integrations/toggle")
        cards.append(Div(
            Div(Span(_KIND_ICON.get(r["kind"], "\U0001F517"), cls="text-2xl"),
                Span("● connected" if conn else "○ available",
                     cls="text-xs " + ("text-green-700" if conn else "text-ink-dim")),
                cls="flex items-center justify-between mb-2"),
            H3(r["name"], cls="text-ink text-lg font-medium"),
            P(r["description"], cls="text-ink-muted text-sm mt-1 mb-3"),
            action,
            cls="p-6 rounded-2xl bg-bg-elevated border border-line"))
    note = P(("Executive / Super may connect integrations." if can
              else "Configuring integrations requires Executive / Super (segregation of duties)."),
             cls="text-sm mt-6 " + ("text-ink-muted" if can else "text-red-700"))
    webhook = Div(
        P("Inbound webhook (live)", cls="text-sm font-medium text-ink mb-2"),
        P(NotStr("POST <code class='px-1 rounded bg-bg-raised'>/api/integrations/invoice</code> with JSON "
                 "<code class='px-1 rounded bg-bg-raised'>{seller, debtor, amount, due_date}</code> "
                 "to ingest an invoice from an external system."),
          cls="text-ink-muted text-sm"),
        cls="mt-8 p-6 rounded-2xl bg-bg-raised/40 border border-line max-w-2xl")
    return app_page("Integrations",
                    Section_(Eyebrow("Back office · Integrations"),
                             Heading(1, "Integrations", cls="mt-4"),
                             P("Accounting, open banking, bureau, e-signature, collections and e-invoice "
                               "connectors, plus a live inbound webhook.", cls="mt-3 text-ink-muted max-w-3xl"),
                             cls="border-t border-line"),
                    Section_(Div(*cards, cls="grid sm:grid-cols-2 lg:grid-cols-3 gap-4"), note, webhook,
                             cls="border-t border-line"),
                    current_path="/app/admin/integrations", lang=get_lang(req),
                    role="admin", subrole=current_subrole(req))


@rt("/app/admin/integrations/toggle", methods=["POST"])
def integrations_toggle(req, name: str = "", csrf: str = ""):
    import hmac
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    g = _guard(req)
    if g:
        return g
    sub = current_subrole(req)
    if sub in CAN_CONFIG and _HAS_DB:
        cur = fetch_one("SELECT connected FROM factorio.integrations WHERE name=%(n)s", {"n": name})
        if cur is not None:
            new = not cur["connected"]
            execute("UPDATE factorio.integrations SET connected=%(c)s, updated_at=now() WHERE name=%(n)s",
                    {"c": new, "n": name})
            log_action("admin", sub, "integration.connect" if new else "integration.disconnect", name, "")
    return RedirectResponse("/app/admin/integrations", status_code=303)


# ── Live inbound webhook: ingest an invoice from an external system ─────────

@rt("/api/integrations/invoice", methods=["POST"])
async def ingest_invoice(req):
    import hmac
    from utils.config import settings
    configured = settings().integration_webhook_token
    supplied = req.headers.get("x-factorio-webhook-token", "")
    if not configured:
        return JSONResponse({"ok": False, "error": "webhook disabled"}, status_code=503)
    if not supplied or not hmac.compare_digest(supplied, configured):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        body = await req.json()
    except Exception:
        try:
            form = await req.form(); body = dict(form)
        except Exception:
            body = {}
    seller = body.get("seller") or "External Seller"
    supplier_email = str(body.get("supplier_email") or "").strip().lower()
    debtor = body.get("debtor") or "External Debtor"
    try:
        amount = float(body.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    due = body.get("due_date") or None
    if not _HAS_DB or amount <= 0 or not supplier_email:
        return JSONResponse({"ok": False, "error": "amount and supplier_email required"}, status_code=400)
    try:
        scope = fetch_one("""SELECT p.supplier_user_id,p.company_id
                              FROM factorio.access_profiles p JOIN factorio.app_users u ON u.email=p.email
                              WHERE lower(p.email)=%(email)s AND p.role='supplier'
                                AND u.status='active' AND u.is_verified=TRUE""",
                          {"email": supplier_email})
        if not scope or not scope.get("supplier_user_id") or not scope.get("company_id"):
            return JSONResponse({"ok": False, "error": "supplier scope not found"}, status_code=404)
        num = "EXT-" + hex(abs(hash((seller, debtor, amount))) % 0xFFFFFF)[2:].upper()
        execute("""INSERT INTO factorio.invoices
                   (invoice_number,seller_id,company_id,debtor_name,description,sector,amount,currency,
                    issue_date,due_date,payment_terms_days,status,risk_grade)
                   VALUES (%(num)s,%(sid)s,%(cid)s,%(deb)s,%(desc)s,'other',%(amt)s,'USD',
                    CURRENT_DATE, COALESCE(%(due)s::date, CURRENT_DATE + 60), 60, 'submitted','B')
                   ON CONFLICT (invoice_number) DO NOTHING""",
                {"num": num, "sid": scope["supplier_user_id"], "cid": scope["company_id"],
                 "deb": debtor, "desc": f"Ingested from external system (seller {seller})",
                 "amt": amount, "due": due})
        return JSONResponse({"ok": True, "invoice_number": num, "status": "submitted"})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
