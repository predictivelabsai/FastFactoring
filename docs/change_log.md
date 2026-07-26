# Change Log

## 2026-07-26 — AI invoice extraction and financing origination

- Added a supplier-facing invoice upload workflow at `/app/seller` for PDF, PNG, JPEG, JSON, and text documents.
- Added Grok/xAI extraction using `prompts/invoice_financing_extraction.md`, temperature-zero JSON output, evidence references, confidence, and review issues.
- Digital PDFs are converted to Markdown locally before extraction. A text-density check detects scanned/image-only PDFs and uses the slower xAI image-understanding path only as a fallback.
- Extracted fields include supplier and debtor identities, registration/tax references, invoice and PO numbers, dates, amount/currency, payment terms, bank account, IBAN, SWIFT, description, sector, and line items.
- Added a human review step. Confirming creates the invoice and open marketplace financing demand in one database transaction.
- Extended invoice storage with extraction/payment metadata while keeping legacy seeded invoices compatible.
- Added three synthetic JSON/PDF invoice pairs under `data/synthetic-invoices/` and a reproducible PDF generator.
- Fixed supplier navigation so **My applications** resolves to the working origination page.
- Updated and regenerated the English and Russian user guides.
