"""Build synthetic invoice PDFs used to demo AI extraction."""

from __future__ import annotations

import json
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "synthetic-invoices"


def build(source: Path) -> Path:
    data = json.loads(source.read_text(encoding="utf-8"))
    target = source.with_suffix(".pdf")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, data["supplier_name"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, f"Registration: {data['supplier_registration']}  Tax ID: {data['supplier_tax_id']}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 12, "INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    for label, value in (
        ("Invoice number", data["invoice_number"]),
        ("Issue date", data["issue_date"]),
        ("Due date", data["due_date"]),
        ("Bill to", data["debtor_name"]),
        ("Customer registration", data["debtor_registration"]),
        ("Description", data["description"]),
        ("Purchase order", data.get("purchase_order_number", "PO-DEMO-2026")),
    ):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(48, 7, f"{label}:", new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(135, 7, str(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_fill_color(31, 93, 67)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 8, "Description", fill=True)
    pdf.cell(0, 8, "Amount", align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 35, 27)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(120, 9, data["description"])
    pdf.cell(0, 9, f"{data['currency']} {data['amount']:,.2f}",
             align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(7)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"TOTAL DUE: {data['currency']} {data['amount']:,.2f}",
             align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Payment details", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for label, key in (
        ("Bank", "supplier_bank_name"),
        ("Account number", "supplier_bank_account"),
        ("IBAN", "supplier_iban"),
        ("SWIFT", "supplier_swift"),
    ):
        pdf.cell(42, 7, f"{label}:")
        pdf.cell(0, 7, data[key], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 5, "Synthetic demonstration invoice. No goods, payment obligation, "
                   "or bank account represented in this document is real.")
    pdf.output(target)
    return target


def main() -> None:
    for source in sorted(SOURCE_DIR.glob("*.json")):
        print(build(source))


if __name__ == "__main__":
    main()
