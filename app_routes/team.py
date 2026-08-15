"""Governance team membership and non-admin role administration."""

from __future__ import annotations

import secrets

from fasthtml.common import Button, Div, Form, H1, H2, Input, Option, P, Select, Span
from starlette.responses import RedirectResponse, Response

from app import rt
from app_routes.shell import app_shell
from utils import accounts
from utils.access import audit, context_for
from utils.i18n import get_lang


def _csrf_ok(req, supplied: str) -> bool:
    expected = str((getattr(req, "session", None) or {}).get("csrf_token") or "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def _role_select(name: str, selected: str = "supplier"):
    return Select(
        *[Option(role.title(), value=role, selected=role == selected)
          for role in ("supplier", "investor", "payer")],
        name=name, cls="border border-line rounded-lg px-3 py-2 bg-white text-sm")


@rt("/app/admin/team", methods=["GET"])
def team_page(req, saved: str = ""):
    ctx = context_for(req)
    if ctx.actual_role != "admin" or ctx.effective_role != "admin":
        return Response("Forbidden", status_code=403)
    try:
        members = accounts.team_rows()
        invitations = accounts.invitation_rows()
    except Exception:
        members, invitations = [], []
    member_cards = []
    for member in members:
        email = str(member.get("email") or "")
        role = str(member.get("role") or "pending")
        control = Span("Admin", cls="text-xs font-semibold") if role == "admin" else Form(
            Input(type="hidden", name="csrf", value=ctx.csrf_token),
            Input(type="hidden", name="email", value=email),
            _role_select("role", role),
            Input(name="payer_registration", value=member.get("payer_registration") or "",
                  placeholder="Payer company number",
                  cls="border border-line rounded-lg px-3 py-2 text-sm") if role == "payer" else None,
            Button("Update", type="submit", cls="px-3 py-2 rounded-lg bg-ink text-white text-xs"),
            action="/app/admin/team/role", method="post", cls="flex items-center gap-2")
        member_cards.append(Div(
            Div(Span(member.get("name") or email, cls="font-medium"),
                Span(email, cls="text-xs text-ink-muted"), cls="flex flex-col"),
            Span(str(member.get("status") or "pending").title(), cls="text-xs text-ink-muted"),
            control, cls="grid md:grid-cols-[1fr_auto_auto] items-center gap-4 p-4 border-b border-line"))
    invite_cards = [Div(
        Span(row.get("email") or "", cls="font-medium"),
        Span(str(row.get("role") or "").title(), cls="text-xs"),
        Span(str(row.get("status") or "").title(), cls="text-xs text-ink-muted"),
        cls="grid grid-cols-[1fr_auto_auto] gap-4 p-3 border-b border-line")
        for row in invitations]
    content = Div(
        Div(Span("Governance", cls="text-xs uppercase tracking-widest text-ink-muted"),
            H1("Team", cls="text-3xl font-semibold mt-3"),
            P("Invite people and assign one operational role. Admin access cannot be delegated.",
              cls="text-ink-muted mt-3"), cls="p-6 md:p-10 border-b border-line"),
        Div(H2("Invite a team member", cls="text-xl font-semibold"),
            P("They can also self-register; an invitation preselects the intended role.",
              cls="text-sm text-ink-muted mt-2 mb-4"),
            Form(Input(type="hidden", name="csrf", value=ctx.csrf_token),
                 Input(name="email", type="email", required=True, placeholder="name@company.com",
                       cls="border border-line rounded-lg px-3 py-2 flex-1 min-w-56"),
                 _role_select("role"),
                 Button("Send invitation", type="submit",
                        cls="px-4 py-2 rounded-lg bg-accent text-white text-sm"),
                 action="/app/admin/team/invite", method="post",
                 cls="flex flex-wrap gap-3"), cls="p-6 md:p-10 border-b border-line"),
        Div(H2("Members", cls="text-xl font-semibold mb-4"),
            Div(*member_cards, cls="bg-white border border-line rounded-xl overflow-hidden"),
            cls="p-6 md:p-10 border-b border-line"),
        Div(H2("Recent invitations", cls="text-xl font-semibold mb-4"),
            Div(*invite_cards, cls="bg-white border border-line rounded-xl overflow-hidden"),
            cls="p-6 md:p-10"),
    )
    return app_shell("Team", content, current_path="/app/admin/team",
                     lang=get_lang(req), role="admin")


@rt("/app/admin/team/invite", methods=["POST"])
def invite_member(req, email: str = "", role: str = "supplier", csrf: str = ""):
    ctx = context_for(req)
    if ctx.actual_role != "admin" or ctx.effective_role != "admin" or not _csrf_ok(req, csrf):
        return Response("Forbidden", status_code=403)
    ok, message = accounts.create_invitation(email, role, ctx.email)
    audit(ctx, "team_invitation_created" if ok else "team_invitation_rejected", email, role)
    return RedirectResponse("/app/admin/team?saved=" + ("1" if ok else "0"), status_code=303)


@rt("/app/admin/team/role", methods=["POST"])
def change_member_role(req, email: str = "", role: str = "supplier",
                       payer_registration: str = "", csrf: str = ""):
    ctx = context_for(req)
    if ctx.actual_role != "admin" or ctx.effective_role != "admin" or not _csrf_ok(req, csrf):
        return Response("Forbidden", status_code=403)
    ok = accounts.update_member_role(email, role, payer_registration)
    audit(ctx, "team_role_changed" if ok else "team_role_rejected", email, role)
    return RedirectResponse("/app/admin/team?saved=" + ("1" if ok else "0"), status_code=303)
