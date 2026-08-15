"""Supplier invoice upload and financing-demand origination."""

from __future__ import annotations

import asyncio
import json
import base64
import html
import re
import secrets
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf
from fasthtml.common import A, Button, Div, Form, Input, Label, NotStr, P, Script, Textarea
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app import rt
from app_routes._shared import app_page, current_role, current_subrole, fmt_uzs
from landing.components import Eyebrow, Heading, Section_
from utils.i18n import get_lang
from utils import ai

try:
    from db import connect, fetch_all
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False


_FIELD = ("w-full mt-1 px-4 py-3 rounded-xl border border-line-bright bg-bg-elevated "
          "text-ink focus:outline-none focus:border-accent")
_SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic-invoices"
_SAMPLES = {
    "manufacturing-invoice.json",
    "logistics-invoice.json",
    "hospitality-invoice.json",
    "manufacturing-invoice.pdf",
    "logistics-invoice.pdf",
    "hospitality-invoice.pdf",
}
_SAMPLE_SLUGS = {
    "manufacturing": "manufacturing-invoice.pdf",
    "logistics": "logistics-invoice.pdf",
    "hospitality": "hospitality-invoice.pdf",
}
_PENDING_OFFERS: dict[str, dict] = {}


def _pdf_slug(supplier: str, factorio_number: str | int, document: str) -> str:
    """Return a portable filename: supplier-factorio-reference-date-document.pdf."""
    raw = unicodedata.normalize("NFKD", str(supplier or "supplier"))
    supplier_slug = re.sub(r"[^a-z0-9]+", "-", raw.encode("ascii", "ignore").decode().lower())
    supplier_slug = supplier_slug.strip("-") or "supplier"
    ref = re.sub(r"[^a-zA-Z0-9]+", "-", str(factorio_number or "pending")).strip("-").lower()
    kind = re.sub(r"[^a-z0-9]+", "-", document.lower()).strip("-")
    return f"{supplier_slug}-factorio-{ref}-{date.today().isoformat()}-{kind}.pdf"


def _pdf_to_markdown(doc: pymupdf.Document) -> str:
    """Convert a digital PDF to page-structured Markdown without OCR."""
    pages = []
    for number, page in enumerate(doc, 1):
        blocks = sorted(page.get_text("blocks"), key=lambda block: (block[1], block[0]))
        body = "\n\n".join(
            block[4].strip() for block in blocks
            if len(block) > 4 and block[4].strip()
        )
        pages.append(f"## Page {number}\n\n{body}")
    return "\n\n".join(pages)


def _parse(payload: str) -> dict:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg}") from exc
    if isinstance(data.get("invoice_data"), dict):
        evidence = data.get("evidence_log") or []
        issues = data.get("issues") or []
        data = data["invoice_data"]
        data["_evidence_log"] = evidence
        data["_issues"] = issues
    required = ("invoice_number", "supplier_name", "debtor_name", "amount",
                "currency", "issue_date", "due_date")
    missing = [key for key in required if data.get(key) in (None, "")]
    if missing:
        raise ValueError("Missing required fields: " + ", ".join(missing))
    try:
        data["amount"] = Decimal(str(data["amount"]))
        data["issue_date"] = date.fromisoformat(str(data["issue_date"]))
        data["due_date"] = date.fromisoformat(str(data["due_date"]))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Amount must be positive and dates must use YYYY-MM-DD.") from exc
    if data["amount"] <= 0 or data["due_date"] <= data["issue_date"]:
        raise ValueError("Amount must be positive and due_date must follow issue_date.")
    financing = data.get("financing") or {}
    advance = Decimal(str(financing.get("advance_rate_pct", 85)))
    if not 1 <= advance <= 100:
        raise ValueError("financing.advance_rate_pct must be between 1 and 100.")
    data["advance_rate_pct"] = advance
    data["funding_goal"] = Decimal(str(financing.get(
        "funding_goal", data["amount"] * advance / Decimal("100"))))
    data["fee_pct_per_30d"] = Decimal(str(financing.get("fee_pct_per_30d", 2)))
    if not 0 < data["funding_goal"] <= data["amount"]:
        raise ValueError("financing.funding_goal must be positive and no greater than the invoice amount.")
    data["risk_grade"] = str(data.get("risk_grade") or "B").upper()
    if data["risk_grade"] not in {"A", "B", "C", "D"}:
        raise ValueError("risk_grade must be A, B, C, or D.")
    return data


def _decode_document(file_data: str, filename: str, mime_type: str) -> dict:
    """Decode a browser-uploaded document and send its content to xAI."""
    if not file_data:
        raise ValueError("Choose an invoice PDF, image, JSON, or text file.")
    try:
        encoded = file_data.split(",", 1)[1] if "," in file_data else file_data
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("The uploaded file could not be decoded.") from exc
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("Invoice files must be 20 MB or smaller.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or mime_type == "application/pdf":
        try:
            doc = pymupdf.open(stream=raw, filetype="pdf")
        except Exception as exc:
            raise ValueError("The PDF could not be read.") from exc
        try:
            page_text = [page.get_text("text").strip() for page in doc]
            sparse_pages = sum(len("".join(text.split())) < 50 for text in page_text)
            total_chars = sum(len("".join(text.split())) for text in page_text)
            is_scanned = bool(doc.page_count) and (
                total_chars < 80 * doc.page_count
                or sparse_pages / doc.page_count >= 0.7
            )
            if is_scanned:
                # Vision is deliberately the slower, more expensive fallback.
                # Four pages covers normal invoices while bounding request size.
                images = []
                for page in list(doc)[:4]:
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7),
                                          colorspace=pymupdf.csRGB, alpha=False)
                    images.append((pix.tobytes("png"), "image/png"))
                return ai.extract_invoice(images=images)
            markdown = _pdf_to_markdown(doc)
            return ai.extract_invoice(text=markdown)
        finally:
            doc.close()
    if suffix in {".png", ".jpg", ".jpeg"} or mime_type in {"image/png", "image/jpeg"}:
        image_mime = "image/png" if suffix == ".png" or mime_type == "image/png" else "image/jpeg"
        return ai.extract_invoice(images=[(raw, image_mime)])
    if suffix in {".json", ".txt"} or mime_type in {"application/json", "text/plain"}:
        return ai.extract_invoice(text=raw.decode("utf-8"))
    raise ValueError("Supported invoice formats are PDF, PNG, JPEG, JSON, and TXT.")


def _create_demand(data: dict, req) -> int:
    """Create the invoice and its open financing demand in one transaction."""
    from utils.access import context_for, preview_side_effect_allowed
    ctx = context_for(req)
    if ctx.effective_role != "supplier" or not ctx.supplier_user_id:
        raise ValueError("A supplier profile must be linked before creating an application.")
    if not preview_side_effect_allowed(ctx):
        raise ValueError("Role preview can write only to the synthetic scenario corpus.")
    with connect() as conn:
        with conn.cursor() as cur:
            seller_id = ctx.supplier_user_id
            company_id = ctx.company_id
            if ctx.preview and not company_id:
                raise ValueError("The synthetic Supplier preview has no linked company.")
            if not company_id:
                registration = str(data.get("supplier_registration") or "").strip()
                if not registration:
                    registration = "SELF-" + str(seller_id)
                cur.execute(
                    """INSERT INTO factorio.companies(name,registration_number,sector,country,address)
                       VALUES (%s,%s,%s,'GB',%s)
                       ON CONFLICT(registration_number) DO UPDATE SET name=EXCLUDED.name
                       RETURNING id""",
                    (data.get("supplier_name") or ctx.name or "Supplier", registration,
                     data.get("sector") or "other", data.get("supplier_registered_address") or ""),
                )
                company_id = cur.fetchone()[0]
                if not ctx.preview:
                    cur.execute("UPDATE factorio.access_profiles SET company_id=%s,updated_at=now() WHERE email=%s",
                                (company_id, ctx.email))
            terms = int((data.get("financing") or {}).get(
                "period_days", (data["due_date"] - data["issue_date"]).days))
            cur.execute("""
                INSERT INTO factorio.invoices
                    (invoice_number, seller_id, company_id, debtor_name, debtor_registration,
                     description, sector, amount, currency, issue_date, due_date,
                     payment_terms_days, status, risk_grade, supplier_name,
                     supplier_registration, supplier_registered_address,
                     supplier_director_name, supplier_contact_email, supplier_contact_phone,
                     supplier_tax_id, supplier_bank_name,
                     supplier_bank_account, supplier_iban, supplier_swift,
                     purchase_order_number, extraction_confidence, extraction_evidence,
                     is_synthetic)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'funding',%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (data["invoice_number"], seller_id, company_id, data["debtor_name"],
                  data.get("debtor_registration") or "", data.get("description") or "",
                  data.get("sector") or "other", data["amount"], data["currency"].upper(),
                  data["issue_date"], data["due_date"], terms, data["risk_grade"],
                  data.get("supplier_name") or "", data.get("supplier_registration") or "",
                  data.get("supplier_registered_address") or "",
                  data.get("supplier_director_name") or "",
                  data.get("supplier_contact_email") or "",
                  data.get("supplier_contact_phone") or "",
                  data.get("supplier_tax_id") or "", data.get("supplier_bank_name") or "",
                  data.get("supplier_bank_account") or "", data.get("supplier_iban") or "",
                  data.get("supplier_swift") or "", data.get("purchase_order_number") or "",
                  data.get("confidence"), json.dumps(data.get("_evidence_log", [])),
                  ctx.preview))
            invoice_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO factorio.invoice_funding
                    (invoice_id, name, description, funding_goal, advance_rate_pct,
                     fee_pct_per_30d, estimated_return_pct, risk_grade, funding_status,
                     target_hold_days, show_in_marketplace)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'open',%s,TRUE)
                RETURNING id
            """, (invoice_id, f"{data['debtor_name']} — {data['invoice_number']}",
                  data.get("description", ""), data["funding_goal"], data["advance_rate_pct"],
                  data["fee_pct_per_30d"], data["fee_pct_per_30d"], data["risk_grade"], terms))
            funding_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO factorio.invoice_updates (invoice_id,title,description,update_type)
                VALUES (%s,'Invoice uploaded','Synthetic invoice JSON validated','created'),
                       (%s,'Funding demand opened','Listed in the marketplace','funding')
            """, (invoice_id, invoice_id))
        conn.commit()
    return funding_id


def _offer_terms(extracted: dict) -> dict:
    inv = extracted.get("invoice_data") or {}
    amount = float(inv.get("amount") or 0)
    financing = inv.get("financing") or {}
    advance_rate = float(financing.get("advance_rate_pct") or 85)
    advance = float(financing.get("funding_goal") or amount * advance_rate / 100)
    advance_rate = advance / amount * 100 if amount else advance_rate
    try:
        issue = date.fromisoformat(str(inv.get("issue_date")))
        due = date.fromisoformat(str(inv.get("due_date")))
        default_days = max(1, (due - issue).days)
    except ValueError:
        default_days = 30
    days = int(financing.get("period_days") or default_days)
    monthly_fee = float(financing.get("fee_pct_per_30d") or 2)
    estimated_fee = advance * monthly_fee / 100 * days / 30
    return {"invoice": inv, "amount": amount, "advance_rate": advance_rate,
            "advance": advance, "days": days, "monthly_fee": monthly_fee,
            "estimated_fee": estimated_fee}


def _offer_html(extracted: dict) -> str:
    terms = _offer_terms(extracted)
    inv = terms["invoice"]
    amount = terms["amount"]; advance_rate = terms["advance_rate"]
    advance = terms["advance"]; days = terms["days"]
    monthly_fee = terms["monthly_fee"]; estimated_fee = terms["estimated_fee"]
    cur = html.escape(str(inv.get("currency") or "USD"))
    supplier = html.escape(str(inv.get("supplier_name") or "your company"))
    invoice = html.escape(str(inv.get("invoice_number") or "invoice"))
    issues = extracted.get("issues") or []
    issue_html = ("<p class='text-xs text-amber-700'>Review: " +
                  html.escape("; ".join(map(str, issues))) + "</p>") if issues else ""
    registration = html.escape(str(inv.get("supplier_registration") or ""))
    address = html.escape(str(inv.get("supplier_registered_address") or ""))
    directors = inv.get("supplier_directors") or []
    director_options = "".join(
        f"<option value='{html.escape(str(item.get('name') or ''))}'>"
        f"{html.escape(str(item.get('name') or ''))}</option>"
        for item in directors if isinstance(item, dict) and item.get("name")
    )
    company_note = ""
    if inv.get("companies_house_verified"):
        company_note = (
            "<p class='text-xs text-green-700'>Companies House match found: "
            f"<b>{html.escape(str(inv.get('companies_house_name') or supplier))}</b>"
            f" ({registration}), status {html.escape(str(inv.get('companies_house_status') or '—'))}. "
            "Please confirm these public registry details.</p>"
        )
    elif inv.get("companies_house_note"):
        company_note = (
            f"<p class='text-xs text-ink-muted'>{html.escape(str(inv['companies_house_note']))}</p>"
        )
    return (
        "<h3 style='font-size:22px;font-weight:700;color:#1F5D43;margin:0 0 8px'>"
        "You’re pre-approved!</h3>"
        f"<p>I extracted invoice <b>{invoice}</b> for <b>{supplier}</b>. "
        "Here is your indicative financing offer:</p>"
        "<table class='offer-table'>"
        f"<tr><td>Invoice value</td><td>{cur} {amount:,.2f}</td></tr>"
        f"<tr><td>You receive today ({advance_rate:.0f}%)</td><td>{cur} {advance:,.2f}</td></tr>"
        f"<tr><td>Invoice term</td><td>{days} days</td></tr>"
        f"<tr><td>Indicative financing fee</td><td>{cur} {estimated_fee:,.2f}</td></tr>"
        "</table>"
        f"<p class='text-xs text-ink-muted'>Financing costs {monthly_fee:.1f}% per 30 days "
        "on the advanced amount. Final terms remain subject to verification.</p>"
        f"{issue_html}"
        "<a class='offer-action secondary' href='/app/supplier/offer-pdf' target='_blank'>Download PDF</a>"
        "<button class='offer-action' onclick='fcAcceptOffer()'>Accept</button>"
        "<button class='offer-action secondary' onclick=\"document.getElementById('offer-change').style.display='block'\">Change</button>"
        "<div id='offer-change' style='display:none;margin-top:10px;padding:12px;background:#fff;border:1px solid #E3DFD2;border-radius:12px'>"
        "<label>Amount to receive today</label>"
        f"<input id='offer-amount' type='number' value='{advance:.2f}' min='1' max='{amount:.2f}' class='chat-input' style='width:180px;margin:0 10px'>"
        "<label>Period (days)</label>"
        f"<input id='offer-days' type='number' value='{days}' min='1' max='365' class='chat-input' style='width:100px;margin:0 10px'>"
        "<button class='offer-action' onclick='fcReviseOffer()'>Update terms</button></div>"
        "<button class='offer-action secondary' onclick=\"document.getElementById('cp-bank-file').click()\">"
        "Upload bank statements (optional)</button>"
        "<button class='offer-action secondary' onclick='fcConnectBank()'>Connect bank (optional)</button>"
        "<div style='margin-top:16px;padding:14px;background:#fff;border:1px solid #E3DFD2;border-radius:12px'>"
        "<p><b>We just need a few additional details</b></p>"
        "<p class='text-xs text-ink-muted'>Add a contact email and confirm the company details below. "
        "This does not change your indicative offer.</p>"
        f"{company_note}"
        "<div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px'>"
        "<label>Contact email<input id='supplier-contact-email' type='email' required "
        "class='chat-input' style='width:100%;margin-top:4px' placeholder='finance@company.com'></label>"
        "<label>Contact phone (optional)<input id='supplier-contact-phone' type='tel' "
        "class='chat-input' style='width:100%;margin-top:4px' placeholder='+44 …'></label>"
        f"<label>Company number<input id='supplier-registration' class='chat-input' "
        f"style='width:100%;margin-top:4px' value='{registration}'></label>"
        f"<label>Active director<select id='supplier-director' class='chat-input' "
        f"style='width:100%;margin-top:4px'><option value=''>Select / confirm</option>{director_options}</select></label>"
        f"<label style='grid-column:1/-1'>Registered address<input id='supplier-address' "
        f"class='chat-input' style='width:100%;margin-top:4px' value='{address}'></label>"
        "</div><button class='offer-action' onclick='fcSaveSupplierDetails()'>Save details</button>"
        "<span id='supplier-details-status' class='text-xs text-ink-muted'></span></div>"
    )


@rt("/app/supplier/extract", methods=["POST"])
async def supplier_chat_extract(req):
    if current_role(req) != "supplier":
        return JSONResponse({"error": "Supplier access required."}, status_code=403)
    form = await req.form()
    try:
        extracted = _decode_document(
            str(form.get("file_data") or ""), str(form.get("filename") or ""),
            str(form.get("mime_type") or ""))
        invoice_data = dict(extracted.get("invoice_data") or {})
        invoice_data.pop("line_items", None)
        evidence = []
        for item in (extracted.get("evidence_log") or [])[:10]:
            if isinstance(item, dict):
                evidence.append({k: str(item.get(k, ""))[:160]
                                 for k in ("field", "value", "excerpt")})
        pending = {
            "invoice_data": invoice_data,
            "evidence_log": evidence,
            "issues": [str(issue)[:180] for issue in (extracted.get("issues") or [])[:8]],
        }
        company_name = str(invoice_data.get("supplier_name") or "")
        company_number = str(invoice_data.get("supplier_registration") or "")
        if company_name and (
            not company_number
            or not invoice_data.get("supplier_registered_address")
            or not invoice_data.get("supplier_directors")
        ):
            try:
                from utils.companies_house import enrich_supplier
                company = await asyncio.to_thread(enrich_supplier, company_name, company_number)
                if company:
                    invoice_data["supplier_registration"] = company["company_number"]
                    invoice_data["supplier_registered_address"] = company["registered_address"]
                    invoice_data["supplier_directors"] = company["directors"]
                    invoice_data["companies_house_name"] = company["company_name"]
                    invoice_data["companies_house_status"] = company["company_status"]
                    invoice_data["companies_house_verified"] = True
                else:
                    invoice_data["companies_house_note"] = (
                        "No confident Companies House match was found; please enter the registration details."
                    )
            except RuntimeError:
                invoice_data["companies_house_note"] = (
                    "Companies House verification is temporarily unavailable; you can enter the details manually."
                )
        token = secrets.token_urlsafe(24)
        if len(_PENDING_OFFERS) >= 100:
            _PENDING_OFFERS.pop(next(iter(_PENDING_OFFERS)), None)
        _PENDING_OFFERS[token] = pending
        req.session["supplier_offer_token"] = token
        return JSONResponse({"ok": True, "html": _offer_html(pending)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


def _pending_offer(req):
    token = req.session.get("supplier_offer_token", "")
    return token, _PENDING_OFFERS.get(token)


@rt("/app/supplier/details", methods=["POST"])
async def supplier_details(req):
    if current_role(req) != "supplier":
        return JSONResponse({"error": "Supplier access required."}, status_code=403)
    _token, extracted = _pending_offer(req)
    if not extracted:
        return JSONResponse({"error": "Upload an invoice first."}, status_code=400)
    form = await req.form()
    email = str(form.get("email") or "").strip()
    if "@" not in email or len(email) > 254:
        return JSONResponse({"error": "Enter a valid contact email."}, status_code=400)
    inv = extracted["invoice_data"]
    inv["supplier_contact_email"] = email
    inv["supplier_contact_phone"] = str(form.get("phone") or "").strip()[:80]
    inv["supplier_registration"] = str(form.get("registration") or "").strip()[:80]
    inv["supplier_registered_address"] = str(form.get("address") or "").strip()[:500]
    inv["supplier_director_name"] = str(form.get("director") or "").strip()[:160]
    return JSONResponse({"ok": True, "message": "Details saved. You can now accept the offer."})


@rt("/app/supplier/change", methods=["POST"])
async def supplier_offer_change(req):
    if current_role(req) != "supplier":
        return JSONResponse({"error": "Supplier access required."}, status_code=403)
    _token, extracted = _pending_offer(req)
    if not extracted:
        return JSONResponse({"error": "Upload an invoice first."}, status_code=400)
    form = await req.form()
    try:
        amount = float(form.get("amount") or 0)
        days = int(form.get("days") or 0)
        invoice_amount = float(extracted["invoice_data"]["amount"])
        if not 0 < amount <= invoice_amount:
            raise ValueError("Financing amount must be positive and no greater than the invoice.")
        if not 1 <= days <= 365:
            raise ValueError("Financing period must be between 1 and 365 days.")
        extracted["invoice_data"]["financing"] = {
            "funding_goal": amount,
            "advance_rate_pct": amount / invoice_amount * 100,
            "fee_pct_per_30d": 2,
            "period_days": days,
        }
        return JSONResponse({"ok": True, "html": _offer_html(extracted)})
    except (TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@rt("/app/supplier/offer-pdf", methods=["GET"])
def supplier_offer_pdf(req):
    if current_role(req) != "supplier":
        return RedirectResponse("/app", status_code=303)
    _token, extracted = _pending_offer(req)
    if not extracted:
        return Response("Upload an invoice first", status_code=400)
    terms = _offer_terms(extracted)
    inv = terms["invoice"]
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "INDICATIVE INVOICE FINANCING TERM SHEET",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 7, "Factorio Ltd | Synthetic demonstration",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    rows = [
        ("Supplier", str(inv.get("supplier_name") or "—")),
        ("Debtor", str(inv.get("debtor_name") or "—")),
        ("Invoice", str(inv.get("invoice_number") or "—")),
        ("Invoice value", f"{inv.get('currency','USD')} {terms['amount']:,.2f}"),
        ("Amount paid today", f"{inv.get('currency','USD')} {terms['advance']:,.2f} ({terms['advance_rate']:.1f}%)"),
        ("Financing period", f"{terms['days']} days"),
        ("Cost per 30 days", f"{terms['monthly_fee']:.2f}% of advanced amount"),
        ("Indicative total fee", f"{inv.get('currency','USD')} {terms['estimated_fee']:,.2f}"),
    ]
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 11); pdf.cell(55, 9, label)
        pdf.set_font("Helvetica", size=11); pdf.cell(0, 9, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12); pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "Indicative only and subject to invoice, debtor, KYC and bank verification. "
                   "This term sheet is not a credit commitment or legal agreement.")
    filename = _pdf_slug(
        str(inv.get("supplier_name") or "supplier"),
        str(inv.get("invoice_number") or "pending"),
        "term-sheet",
    )
    return Response(bytes(pdf.output()), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@rt("/app/supplier/accept", methods=["POST"])
def supplier_chat_accept(req):
    if current_role(req) != "supplier":
        return JSONResponse({"error": "Supplier access required."}, status_code=403)
    token, extracted = _pending_offer(req)
    if not isinstance(extracted, dict):
        return JSONResponse({"error": "Upload an invoice first."}, status_code=400)
    if not (extracted.get("invoice_data") or {}).get("supplier_contact_email"):
        return JSONResponse(
            {"error": "Please add and save a contact email before accepting the offer."},
            status_code=400,
        )
    try:
        data = _parse(json.dumps(extracted))
        funding_id = _create_demand(data, req)
        _PENDING_OFFERS.pop(token, None)
        req.session.pop("supplier_offer_token", None)
        contract = f"/app/supplier/contract/{funding_id}"
        return JSONResponse({"ok": True, "html": (
            f"<p>Your application is ready. Financing demand <b>#{funding_id}</b> was created.</p>"
            f"<a class='offer-action' href='{contract}' target='_blank'>Download financing contract</a>"
            "<a class='offer-action secondary' href='/app/supplier'>View My applications</a>"
            "<p class='text-xs text-ink-muted mt-2'>You can still upload bank statements or connect "
            "your bank later if additional verification is requested.</p>"
        )})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@rt("/app/supplier/contract/{funding_id}", methods=["GET"])
def supplier_contract(req, funding_id: int):
    if current_role(req) != "supplier":
        return RedirectResponse("/app", status_code=303)
    from db import fetch_one
    from utils.access import context_for
    ctx = context_for(req)
    row = fetch_one("""
        SELECT i.invoice_number, i.supplier_name, i.debtor_name, i.amount, i.currency,
               i.issue_date, i.due_date, f.id funding_id, f.funding_goal,
               f.advance_rate_pct, f.fee_pct_per_30d
        FROM factorio.invoice_funding f JOIN factorio.invoices i ON i.id=f.invoice_id
        WHERE f.id=%(f)s AND i.seller_id=%(seller)s
    """, {"f": funding_id, "seller": ctx.supplier_user_id})
    if not row:
        return Response("Contract not found", status_code=404)
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "INVOICE FINANCING AGREEMENT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, f"Synthetic demo contract | Application #{funding_id}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", size=11)
    supplier = row["supplier_name"] or "Supplier company"
    paragraphs = [
        f"This agreement is between Factorio Ltd (the Financier) and {supplier} (the Supplier).",
        f"The Supplier assigns receivable {row['invoice_number']} issued to {row['debtor_name']}, "
        f"with face value {row['currency']} {float(row['amount']):,.2f} and due date {row['due_date']}.",
        f"Subject to verification, Factorio will advance {float(row['advance_rate_pct']):.0f}% of "
        f"the invoice value: {row['currency']} {float(row['funding_goal']):,.2f}.",
        f"The indicative financing fee is {float(row['fee_pct_per_30d']):.2f}% per 30 days on the "
        "advanced amount. The debtor will pay the assigned invoice into Factorio's collection account.",
        "The remaining invoice balance, less financing fees and any agreed charges, will be remitted "
        "to the Supplier after payment by the debtor.",
        "This synthetic agreement is for demonstration only. It creates no legal obligation, credit "
        "commitment, assignment, security interest, or payment instruction.",
    ]
    for idx, text in enumerate(paragraphs, 1):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(9, 7, f"{idx}.", new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(170, 7, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    pdf.ln(8)
    pdf.cell(85, 7, "For Factorio Ltd: __________________")
    pdf.cell(0, 7, f"For {supplier[:34]}: __________________", new_x="LMARGIN", new_y="NEXT")
    data = bytes(pdf.output())
    filename = _pdf_slug(supplier, funding_id, "financing-contract")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


def _page(req, message="", error="", payload="", issues=None):
    rows = []
    if _HAS_DB:
        try:
            rows = fetch_all("""
                SELECT i.invoice_number, i.debtor_name, i.amount, i.currency, f.id funding_id
                FROM factorio.invoices i JOIN factorio.invoice_funding f ON f.invoice_id=i.id
                ORDER BY f.created_at DESC LIMIT 8
            """)
        except Exception:
            pass
    recent = Div(*[
        P(A(r["invoice_number"], href=f"/app/marketplace/{r['funding_id']}", cls="text-accent"),
          f" · {r['debtor_name']} · {r['currency']} {float(r['amount']):,.2f}",
          cls="text-sm py-2 border-b border-line")
        for r in rows
    ]) if rows else P("No financing demands yet.", cls="text-ink-muted text-sm")
    upload = Form(
        Label("Invoice document", cls="text-sm text-ink-muted"),
        Input(type="file", accept=".pdf,.png,.jpg,.jpeg,.json,.txt", id="invoice-file",
              required=True, cls=_FIELD),
        Input(type="hidden", name="file_data", id="invoice-data"),
        Input(type="hidden", name="filename", id="invoice-name"),
        Input(type="hidden", name="mime_type", id="invoice-mime"),
        Button("Extract invoice fields with AI", type="submit",
               cls="mt-4 px-5 py-3 rounded-full bg-accent text-bg font-medium"),
        method="post", action="/app/seller/extract",
    )
    review = Form(
        Label("Review extracted fields before creating the demand",
              cls="text-sm text-ink-muted"),
        Textarea(payload, name="payload", id="invoice-json", rows="20", required=True,
                 cls=_FIELD),
        Button("Create financing demand", type="submit",
               cls="mt-4 px-5 py-3 rounded-full bg-accent text-bg font-medium"),
        method="post", action="/app/seller",
    ) if payload else None
    samples = P(
        "Samples: ",
        A("manufacturing PDF", href="/app/seller/sample/manufacturing",
          download=True, cls="text-accent"), " · ",
        A("logistics PDF", href="/app/seller/sample/logistics",
          download=True, cls="text-accent"), " · ",
        A("hospitality PDF", href="/app/seller/sample/hospitality",
          download=True, cls="text-accent"),
        cls="text-sm text-ink-muted mt-3",
    )
    script = Script(NotStr("""
document.getElementById('invoice-file').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  document.getElementById('invoice-name').value = file.name;
  document.getElementById('invoice-mime').value = file.type;
  document.getElementById('invoice-data').value = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
});
"""))
    return app_page(
        "My applications",
        Section_(Eyebrow("Supplier · Origination"),
                 Heading(1, "Upload an invoice", cls="mt-4"),
                 P("Upload a synthetic invoice and create an open financing demand in one step.",
                   cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
        Section_(
            P(message, cls="mb-4 text-green-700") if message else None,
            P(error, cls="mb-4 text-red-700") if error else None,
            Div(*[P(f"Review: {issue}", cls="text-sm text-amber-700 mb-1")
                  for issue in (issues or [])], cls="mb-4") if issues else None,
            Div(Div(upload, samples, review, cls="lg:col-span-2"),
                Div(P("Recent demands", cls="font-medium mb-2"), recent),
                cls="grid lg:grid-cols-3 gap-8"),
            script, cls="border-t border-line"),
        current_path="/app/seller", lang=get_lang(req), role="supplier",
        subrole=current_subrole(req),
    )


@rt("/app/seller", methods=["GET"])
def seller_origination(req):
    if current_role(req) != "supplier":
        return RedirectResponse("/app", status_code=303)
    return RedirectResponse("/app", status_code=303)


@rt("/app/seller/sample/{name}", methods=["GET"])
def seller_invoice_sample(req, name: str):
    filename = _SAMPLE_SLUGS.get(name, name if name in _SAMPLES else "")
    if current_role(req) != "supplier" or not filename:
        return RedirectResponse("/app/seller", status_code=303)
    media_type = "application/pdf" if filename.endswith(".pdf") else "application/json"
    return FileResponse(_SAMPLE_DIR / filename, media_type=media_type, filename=filename)


@rt("/app/seller", methods=["POST"])
def seller_origination_post(req, payload: str = ""):
    if current_role(req) != "supplier":
        return RedirectResponse("/app", status_code=303)
    try:
        data = _parse(payload)
        funding_id = _create_demand(data, req)
        return _page(req, f"Created financing demand #{funding_id} for {data['invoice_number']}.")
    except Exception as exc:  # validation and database constraint errors are shown in the demo UI
        return _page(req, error=str(exc), payload=payload)


@rt("/app/seller/extract", methods=["POST"])
def seller_invoice_extract(req, file_data: str = "", filename: str = "", mime_type: str = ""):
    if current_role(req) != "supplier":
        return RedirectResponse("/app", status_code=303)
    try:
        extracted = _decode_document(file_data, filename, mime_type)
        payload = json.dumps(extracted, indent=2, ensure_ascii=False)
        return _page(req, message=f"Extracted fields from {filename}. Review them before creating demand.",
                     payload=payload, issues=extracted.get("issues"))
    except Exception as exc:
        return _page(req, error=str(exc))
