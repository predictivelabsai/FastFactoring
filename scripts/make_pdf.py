"""Generate a Factorio reference-product tour PDF from demo screenshots.

Output: docs/fastfactoring-reference-product-tour.pdf

Slide-deck format (landscape, 16:9).

Usage:
    python -m scripts.make_pdf
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image as RLImage, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "docs" / "fastfactoring-reference-product-tour.pdf"

SLIDE = (33.87 * cm, 19.05 * cm)

BG         = HexColor("#F7F6F1")
INK        = HexColor("#14231B")
INK_MUTED  = HexColor("#415046")
INK_DIM    = HexColor("#7A867E")
ACCENT     = HexColor("#1F5D43")
RULE       = HexColor("#E3DFD2")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "hero":     ParagraphStyle("hero",     parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=42, leading=50, textColor=INK, alignment=TA_CENTER,
                                   spaceAfter=10),
        "hero_sub": ParagraphStyle("hero_sub", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=16, leading=22, textColor=INK_MUTED, alignment=TA_CENTER,
                                   spaceAfter=16),
        "eyebrow":  ParagraphStyle("eyebrow",  parent=ss["Normal"], fontName="Helvetica-Bold",
                                   fontSize=10, leading=12, textColor=ACCENT, spaceAfter=4,
                                   letterSpacing=1.2),
        "title":    ParagraphStyle("title",    parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=28, leading=34, textColor=INK, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=13, leading=18, textColor=INK_MUTED, spaceAfter=14),
        "body":     ParagraphStyle("body",     parent=ss["BodyText"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=INK, alignment=TA_LEFT,
                                   spaceAfter=4),
        "caption":  ParagraphStyle("caption",  parent=ss["Italic"], fontName="Helvetica-Oblique",
                                   fontSize=9, leading=11, textColor=INK_DIM, alignment=TA_CENTER,
                                   spaceBefore=2),
        "bullet":   ParagraphStyle("bullet",   parent=ss["BodyText"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=INK, leftIndent=12,
                                   bulletIndent=0),
    }


def _fit_image(path: Path, max_w_mm: float, max_h_mm: float) -> RLImage:
    img = Image.open(path)
    w, h = img.size
    ratio = min(max_w_mm * mm / w, max_h_mm * mm / h)
    return RLImage(str(path), width=w * ratio, height=h * ratio)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, SLIDE[0], SLIDE[1], fill=1, stroke=0)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(1.5 * cm, 1 * cm, SLIDE[0] - 1.5 * cm, 1 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_DIM)
    canvas.drawString(1.5 * cm, 0.55 * cm, "Factorio — powered by open-source FastFactoring")
    canvas.drawRightString(SLIDE[0] - 1.5 * cm, 0.55 * cm, f"{doc.page}")
    canvas.restoreState()


def _slide_frame(doc):
    return Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main",
        leftPadding=6, rightPadding=6,
        topPadding=0, bottomPadding=0,
    )


def _hero_slide(styles):
    return [
        Spacer(1, 40 * mm),
        Paragraph("Factorio", styles["hero"]),
        Paragraph("Invoice financing for growing businesses.", styles["hero_sub"]),
        Paragraph("Submit invoices · Get funded in days · Grow faster", styles["hero_sub"]),
        PageBreak(),
    ]


def _slide(styles, *, eyebrow: str, title: str, subtitle: str,
           bullets: list[str], screenshot: str, caption: str = None) -> list:
    left_cell = [
        Paragraph(eyebrow.upper(), styles["eyebrow"]),
        Paragraph(title, styles["title"]),
        Paragraph(subtitle, styles["subtitle"]),
    ]
    for b in bullets:
        left_cell.append(Paragraph(f"• {b}", styles["bullet"]))

    shot_path = SHOTS / screenshot
    if shot_path.exists():
        img = _fit_image(shot_path, max_w_mm=170, max_h_mm=135)
        right_cell = [img]
        if caption:
            right_cell.append(Paragraph(caption, styles["caption"]))
    else:
        right_cell = [Paragraph(f"[missing {screenshot}]", styles["caption"])]

    t = Table(
        [[left_cell, right_cell]],
        colWidths=[120 * mm, 180 * mm],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 3 * mm), t, PageBreak()]


def _agenda_slide(styles):
    rows = [
        ["01", "Landing pages", "Homepage, For Sellers, For Investors, How it Works, Pricing, Contact"],
        ["02", "Dashboard", "Platform-wide stats: total funded, invoices, active funding, investors"],
        ["03", "Marketplace", "Browse open invoice funding opportunities with risk grades and returns"],
        ["04", "Invoice detail", "Full debtor info, funding progress, advance rate, fee structure"],
        ["05", "Portfolio", "Investor positions, expected returns, status tracking"],
        ["06", "Multilingual", "English, O’zbekcha, and Russian with one-click switching"],
    ]
    t = Table(rows, colWidths=[20 * mm, 130 * mm, 150 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 12),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 14),
        ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 12),
        ("TEXTCOLOR", (0, 0), (0, -1), ACCENT),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("TEXTCOLOR", (2, 0), (2, -1), INK_MUTED),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [
        Spacer(1, 8 * mm),
        Paragraph("TOUR", styles["eyebrow"]),
        Paragraph("What you’ll see", styles["title"]),
        Paragraph("The full platform in six sections.", styles["subtitle"]),
        Spacer(1, 6 * mm),
        t,
        PageBreak(),
    ]


def _closing_slide(styles):
    cta_body = ParagraphStyle(
        "cta_body", parent=styles["body"], alignment=TA_CENTER, fontSize=15, leading=22,
    )
    cta_meta = ParagraphStyle(
        "cta_meta", parent=styles["caption"], alignment=TA_CENTER, fontSize=11, leading=16,
        textColor=INK_MUTED,
    )
    return [
        Spacer(1, 35 * mm),
        Paragraph("GET STARTED", styles["eyebrow"]),
        Paragraph("Turn your invoices into working capital.", ParagraphStyle(
            "cta_title", parent=styles["title"], alignment=TA_CENTER, fontSize=38, leading=46,
        )),
        Spacer(1, 6 * mm),
        Paragraph(
            "Apply in minutes. Get an offer within 1–3 working days. "
            "No commitment, no hidden fees.",
            cta_body,
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "<b>hello@factorio.co.uk</b> &nbsp;·&nbsp; factorio.co.uk/contact",
            cta_meta,
        ),
        PageBreak(),
    ]


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    doc = BaseDocTemplate(
        str(OUT), pagesize=SLIDE,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1 * cm, bottomMargin=1.5 * cm,
        title="Factorio — FastFactoring Reference Product Tour",
        author="Predictive Labs",
    )
    doc.addPageTemplates([PageTemplate(id="slide", frames=[_slide_frame(doc)], onPage=_footer)])

    story: list = []
    story += _hero_slide(styles)
    story += _agenda_slide(styles)

    story += _slide(
        styles,
        eyebrow="01 · Landing",
        title="Invoice financing for growing businesses",
        subtitle="Turn unpaid invoices into working capital in days, not months.",
        bullets=[
            "Hero with key stats: 85% advance rate, 1–3 day turnaround, 5 sectors supported, 3 languages.",
            "Four-step process: Submit → Verify → Fund → Settle.",
            "Sector-specific cards for manufacturing, wholesale, construction, logistics, services.",
            "Twelve enabled languages with administrator-controlled availability.",
        ],
        screenshot="01-home-en.png",
        caption="Factorio reference-product homepage (English)",
    )
    story += _slide(
        styles,
        eyebrow="02 · Dashboard",
        title="Platform overview at a glance",
        subtitle="Key metrics for the invoice financing platform.",
        bullets=[
            "Total funded volume in UZS across all invoices.",
            "Count of invoices submitted and currently seeking funding.",
            "Number of active investors on the platform.",
            "Quick links to marketplace and portfolio.",
        ],
        screenshot="07-dashboard-en.png",
        caption="Dashboard with platform stats",
    )
    story += _slide(
        styles,
        eyebrow="03 · Marketplace",
        title="Browse open invoice funding opportunities",
        subtitle="Filter and invest in verified commercial invoices.",
        bullets=[
            "Card-based layout with debtor name, sector, risk grade (A–D).",
            "Live funding progress bar and percentage funded.",
            "Key metrics per card: advance rate, fee per 30 days, estimated return.",
            "Click ‘Invest’ to see the full invoice detail page.",
        ],
        screenshot="08-marketplace-en.png",
        caption="Marketplace with 14 open invoices",
    )
    story += _slide(
        styles,
        eyebrow="04 · Invoice Detail",
        title="Full transparency on every invoice",
        subtitle="All the data you need to make an investment decision.",
        bullets=[
            "Debtor and seller company details with country and registration.",
            "Funding progress bar with amount raised vs goal.",
            "Invoice amount, advance rate, fee structure, estimated return.",
            "Due date, risk grade, and payment terms clearly displayed.",
        ],
        screenshot="09-marketplace-detail-en.png",
        caption="Invoice detail page for Ipoteka Bank",
    )
    story += _slide(
        styles,
        eyebrow="05 · Portfolio",
        title="Track your investment positions",
        subtitle="Real-time view of all investments and expected returns.",
        bullets=[
            "Summary cards: total invested, total expected returns, active and total positions.",
            "Full table with invoice number, debtor, amounts, due date, risk grade, status.",
            "Status badges: pending, confirmed, settled, defaulted.",
            "All amounts in UZS with Uzbek company debtors.",
        ],
        screenshot="10-portfolio-en.png",
        caption="Investor portfolio with 62 positions",
    )
    story += _slide(
        styles,
        eyebrow="06 · Multilingual",
        title="Three languages, one click",
        subtitle="Flag switcher in the navbar — English, O’zbekcha, Russian.",
        bullets=[
            "Cookie-based language preference persists across sessions.",
            "All 150+ UI strings translated across landing pages and app.",
            "Uzbek debtors and UZS currency throughout the platform.",
            "Designed for the Uzbekistan market with local business context.",
        ],
        screenshot="11-home-uz.png",
        caption="Homepage in O’zbekcha",
    )

    story += _closing_slide(styles)

    doc.build(story)
    print(f"Wrote {OUT}  ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build()
