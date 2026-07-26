# Invoice Extraction Test Notes

## Quick manual test

1. Sign in as **Supplier** at <https://factorio.co.uk/login>.
2. Open <https://factorio.co.uk/app/seller>.
3. Download a sample PDF from the page and upload it.
4. Click **Extract invoice fields with AI**.
5. Review the JSON, then click **Create financing demand**.
6. Follow the new demand link or open <https://factorio.co.uk/app/marketplace>.

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
one open `factorio.invoice_funding` row, two timeline events, and a visible marketplace
listing. Bank details and extraction evidence are retained on the invoice record.
