"""Invoice PDF generation + a vendored pdf.js viewer (ai-indurent pattern).

- `/pdfjs/<file>` serves the vendored pdf.js runtime + the self-contained
  `viewer.html` (canvas render + text-layer search highlighting).
- `/app/invoice-pdf/<invoice_number>` renders a synthetic invoice PDF on the fly
  (WeasyPrint) from the invoice's real row, cached in-process.

The shell exposes a slide-in right pane whose iframe points at
`/pdfjs/viewer.html?file=/app/invoice-pdf/<num>#search=<term>` — clicking an
invoice's "View" opens it there with the debtor name highlighted.
"""

from __future__ import annotations

from pathlib import Path

from starlette.responses import Response

from app import rt

try:
    from db import fetch_one
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

PDFJS_DIR = Path(__file__).resolve().parents[1] / "static" / "pdfjs"
_ALLOWED = {"pdf.min.mjs", "pdf.worker.min.mjs"}

_pdf_cache: dict[str, bytes] = {}


@rt("/pdfjs/viewer")
def pdfjs_viewer():
    # served extension-less so the static handler doesn't intercept a .html path
    p = PDFJS_DIR / "viewer.html"
    if not p.exists():
        return Response("not found", status_code=404)
    return Response(p.read_bytes(), media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=86400"})


@rt("/pdfjs/{fname}")
def pdfjs_asset(fname: str):
    if fname not in _ALLOWED:
        return Response("not found", status_code=404)
    p = PDFJS_DIR / fname
    if not p.exists():
        return Response("not found", status_code=404)
    return Response(p.read_bytes(), media_type="text/javascript",
                    headers={"Cache-Control": "public, max-age=86400"})


def _s(x) -> str:
    """Sanitise to latin-1 for fpdf2 core fonts."""
    return str(x if x is not None else "").encode("latin-1", "replace").decode("latin-1")


def _invoice_pdf_bytes(r: dict) -> bytes:
    """Render a clean invoice PDF with fpdf2 (pure-Python — no system deps)."""
    from fpdf import FPDF
    from utils.money import fmt_money

    face = float(r["amount"] or 0)
    seller = _s(r.get("seller_company") or "Supplier Ltd")
    num = _s(r["invoice_number"])
    debtor = _s(r["debtor_name"])
    terms = r.get("payment_terms_days") or 60
    li = [("Goods / services supplied per contract", round(face * 0.82, 2)),
          ("Delivery & handling", round(face * 0.18, 2))]

    GREEN, GREY, INK = (31, 93, 67), (107, 114, 128), (20, 35, 27)
    p = FPDF(format="A4")
    p.set_auto_page_break(True, 18)
    p.add_page()
    p.set_margins(18, 16, 18)

    # header (row 1: seller + INVOICE, row 2: subtitle + number)
    p.set_font("Helvetica", "B", 20); p.set_text_color(*GREEN)
    p.cell(120, 9, seller)
    p.set_font("Helvetica", "", 9); p.set_text_color(*GREY)
    p.cell(0, 9, "INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
    p.set_font("Helvetica", "", 9); p.set_text_color(*GREY)
    p.cell(120, 5, "Supplier - issued via Factorio")
    p.set_font("Helvetica", "B", 12); p.set_text_color(*INK)
    p.cell(0, 5, num, align="R", new_x="LMARGIN", new_y="NEXT")
    p.ln(4); p.set_draw_color(*GREEN); p.set_line_width(0.8)
    p.line(18, p.get_y(), 192, p.get_y()); p.ln(7)

    p.set_font("Helvetica", "B", 15); p.set_text_color(*INK)
    p.cell(0, 9, f"Invoice {num}", new_x="LMARGIN", new_y="NEXT"); p.ln(3)

    # meta row (four columns)
    cols = [("BILL TO (DEBTOR)", debtor), ("ISSUE DATE", _s(r.get("issue_date"))),
            ("DUE DATE", _s(r.get("due_date"))), ("TERMS", f"{terms} days")]
    y = p.get_y()
    for i, (lbl, val) in enumerate(cols):
        x = 18 + i * 44
        p.set_xy(x, y); p.set_font("Helvetica", "", 7.5); p.set_text_color(*GREY)
        p.cell(44, 4, lbl)
        p.set_xy(x, y + 5); p.set_font("Helvetica", "B" if i == 0 else "", 11); p.set_text_color(*INK)
        p.cell(44, 6, val)
    p.set_y(y + 16)

    # line-item table
    p.set_fill_color(*GREEN); p.set_text_color(255, 255, 255); p.set_font("Helvetica", "B", 10)
    p.cell(96, 8, " Description", fill=True)
    p.cell(20, 8, "Qty", align="C", fill=True)
    p.cell(29, 8, "Unit", align="R", fill=True)
    p.cell(29, 8, "Amount ", align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    p.set_text_color(*INK); p.set_font("Helvetica", "", 10)
    for desc, amt in li:
        p.cell(96, 8, " " + _s(desc), border="B")
        p.cell(20, 8, "1", align="C", border="B")
        p.cell(29, 8, fmt_money(amt), align="R", border="B")
        p.cell(29, 8, fmt_money(amt) + " ", align="R", border="B", new_x="LMARGIN", new_y="NEXT")
    p.ln(4)
    p.set_font("Helvetica", "B", 13); p.set_text_color(*GREEN)
    p.cell(0, 8, f"Total due: {fmt_money(face)}", align="R", new_x="LMARGIN", new_y="NEXT")

    p.ln(10); p.set_font("Helvetica", "", 8.5); p.set_text_color(*GREY)
    p.multi_cell(0, 4.6,
        f"Payment due within {terms} days of the issue date to the account on file. This invoice may be "
        "assigned to a financing party; on assignment, payment must be made to the assignee's collection "
        "account. Buyer-confirmed on the SoliqOnline e-invoice network. Generated for demonstration - "
        "synthetic data.")
    out = p.output()
    return bytes(out)


@rt("/app/invoice-pdf/{invoice_number}")
def invoice_pdf(req, invoice_number: str):
    from utils.access import context_for
    ctx = context_for(req)
    if not _HAS_DB:
        return Response("db unavailable", status_code=503)
    role_predicate = {
        "admin": "TRUE",
        "supplier": "i.seller_id=%(subject)s",
        "payer": "i.debtor_registration=%(registration)s",
        "investor": "EXISTS (SELECT 1 FROM factorio.invoice_funding f JOIN factorio.investments x ON x.funding_id=f.id WHERE f.invoice_id=i.id AND x.investor_id=%(subject)s)",
    }.get(ctx.effective_role, "FALSE")
    params = {"n": invoice_number,
              "subject": ctx.supplier_user_id if ctx.effective_role == "supplier" else ctx.investor_user_id,
              "registration": ctx.payer_registration}
    authorized = fetch_one(f"SELECT i.id FROM factorio.invoices i WHERE i.invoice_number=%(n)s AND {role_predicate}", params)
    if not authorized:
        return Response("invoice not found", status_code=404)
    if invoice_number in _pdf_cache:
        data = _pdf_cache[invoice_number]
    else:
        r = fetch_one("""
            SELECT i.invoice_number, i.debtor_name, i.amount, i.currency, i.issue_date,
                   i.due_date, i.payment_terms_days, i.sector, i.risk_grade,
                   c.name AS seller_company
            FROM factorio.invoices i
            LEFT JOIN factorio.companies c ON c.id = i.company_id
            WHERE i.invoice_number = %(n)s
        """, {"n": invoice_number})
        if not r:
            return Response("invoice not found", status_code=404)
        try:
            data = _invoice_pdf_bytes(r)
        except Exception as e:  # noqa: BLE001
            return Response(f"pdf error: {e}", status_code=500)
        _pdf_cache[invoice_number] = data
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{invoice_number}.pdf"'})
