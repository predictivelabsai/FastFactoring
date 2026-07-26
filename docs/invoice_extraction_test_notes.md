# Invoice Extraction Test Notes

## Quick manual test

1. Sign in as **Supplier** at <https://factorio.co.uk/login>.
2. The default <https://factorio.co.uk/app> view should be **Factorio AI**, asking
   the supplier to upload an invoice.
3. Click the paperclip and upload a sample PDF from `data/synthetic-invoices/`.
4. Review the inline financing offer and accept it.
5. Open <https://factorio.co.uk/app/supplier> and download the generated contract.

Expected extracted values include invoice number, supplier and debtor, amount and
currency, issue/due dates, registration/tax references, bank account, IBAN, SWIFT,
confidence, evidence, and issues.

## Extraction-path checks

- **Digital PDF:** use any included sample. It should be converted locally to
  page-structured Markdown and sent to xAI as text.
- **Scanned PDF:** print a sample to an image-only PDF. It should be detected as
  scanned and rendered to PNG for xAI vision.
- **Image:** upload a PNG/JPEG screenshot of an invoice; it should use vision directly.
- **JSON/TXT:** upload invoice text; it should use text extraction without vision.

## Validation and failure checks

- Remove a required value in the review JSON: submission should identify the missing field.
- Set `due_date` before `issue_date`: submission should be rejected.
- Set a negative amount or advance rate above 100%: submission should be rejected.
- Upload the same invoice twice: the unique invoice number should prevent a duplicate.
- Upload an unsupported file or a file over 20 MB: extraction should be rejected.
- Temporarily omit `XAI_API_KEY`: the page should report that extraction is unavailable.

## Successful result

A successful submission creates one `factorio.invoices` row with status `funding`,
one open `factorio.invoice_funding` row, two timeline events, and a one-page synthetic
contract between Factorio Ltd and the extracted supplier. Bank details and extraction
evidence are retained on the invoice record. Supplier navigation should contain only
**Factorio AI** and **My applications**—not Triage or Marketplace.
