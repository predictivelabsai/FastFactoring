# Factorio — User Guide
## Invoice financing, end to end

Generated 2026-07-26 · Live at **factorio.co.uk**

Factorio is an invoice-financing (factoring) marketplace. Businesses sell their unpaid invoices for cash today; investors fund those invoices for a short-term, asset-backed return. This guide walks through every screen — the public site and the investor product app — one screen per slide.

---

<p class="eyebrow">Overview</p>

## What Factorio is

![Factorio homepage](img/en-01-landing.png)

- An invoice-financing marketplace connecting two sides: **sellers** who need cash now and **investors** seeking short-term, asset-backed returns.
- One site serves both — a marketing front and an HTMX-driven product app.
- The hero summarizes the model: advance rate, days-to-funding, sectors served and total funded volume (UZS).
- Fully trilingual — English, Oʻzbekcha and Russian — switched from the top navigation.

---

<p class="eyebrow">For sellers</p>

## Turn invoices into working capital

![For Sellers page](img/en-02-for-sellers.png)

- Get a large share of an invoice advanced in days instead of waiting 30–120 days for the debtor to pay.
- The seller journey: submit an invoice → get it verified and risk-graded → receive the advance → settle when the debtor pays.
- Factoring, not a loan — no new debt on the balance sheet; funding scales with sales.
- Built for manufacturing, wholesale, construction, logistics and services.

---

<p class="eyebrow">For investors</p>

## Short-term, asset-backed returns

![For Investors page](img/en-03-for-investors.png)

- Fund verified invoices and earn a fee/return over a short hold — often just weeks.
- Diversify across debtors, sectors and risk grades (A–D).
- Returns are tied to real receivables, not market speculation.
- Leads into the investor app — dashboard, marketplace and portfolio.

---

<p class="eyebrow">How it works</p>

## Four steps, end to end

![How It Works page](img/en-04-how-it-works.png)

- **Submit** — a seller uploads an invoice and company details.
- **Verify** — Factorio checks the debtor and assigns a risk grade and pricing.
- **Fund** — the invoice appears on the marketplace; investors fund it to its goal.
- **Settle** — when the debtor pays, principal + interest are distributed and the position closes.

---

<p class="eyebrow">How the money moves</p>

## Where every party's money comes from

![Money & payment flow — seller, payer, platform, capital](img/en-15-money-flow.png){: .diagram }

<p class="caption">Money & payment flow — seller, payer, platform, capital</p>

- The **seller** delivers goods and issues a SoliqOnline e-invoice; the **payer (debtor)** owes the invoice amount.
- The platform advances ~85% to the seller now, funded by the **capital source** — the bank's balance sheet, investors, or the DIFC SPV.
- At maturity the **payer pays 100%** into the collection account; the seller receives the net balance, the capital source gets principal + return, and the platform keeps a volume-based fee.
- The flow is identical whoever funds it — which is what makes the investor / SPV layer pluggable.

---

<p class="eyebrow">Journey · Borrower (origination)</p>

## The seller's journey, end to end

![From sign-up to advance in 24–48 hours](img/en-16-origination-journey.png){: .diagram }

<p class="caption">From sign-up to advance in 24–48 hours</p>

- Sign up (bank KYC) → invoice auto-imported from SoliqOnline → request financing in an AI-triage chat.
- Debtor scoring returns indicative terms; the bank approves in one click; collateral is registered with the CBU in under an hour.
- The advance lands in the seller's account in 24–48 hours — no branch visit, no paper.

---

<p class="eyebrow">Journey · Investor</p>

## The investor's journey, end to end

![From onboarding to distribution](img/en-17-investor-journey.png){: .diagram }

<p class="caption">From onboarding to distribution</p>

- Onboard (KYC / accreditation) → commit capital via the marketplace or the SPV → auto-invest or pick invoices.
- Hold the position with AI portfolio reporting on demand; when the debtor pays at maturity, principal + return are distributed.
- **Decomposable:** the origination piece (bank-funded) can launch first; the investor marketplace and SPV plug in later, independently.

---

<p class="eyebrow">Pricing</p>

## Transparent, per-invoice fees

![Pricing page](img/en-05-pricing.png)

- Pricing is per invoice — a fee per 30 days against the advanced amount, with no hidden charges.
- Shows the headline advance rate and worked example economics.
- No subscription and no commitment to submit an invoice.
- A clear breakdown so both sides understand the return and the cost.

---

<p class="eyebrow">Contact</p>

## Get in touch

![Contact page](img/en-06-contact.png)

- A contact page for sellers and investors to reach the Factorio team.
- Shows the contact email and a simple enquiry form.
- The entry point to start onboarding.

---

<p class="eyebrow">Investor app · Dashboard</p>

## Your personalized overview

![Investor dashboard](img/en-07-dashboard.png)

- The `/app` home greets the current investor and leads with their own KPIs: portfolio value, net annual return, earned-to-date and the next settlement.
- A recent-activity feed surfaces notifications — fundings, settlements and updates.
- Quick actions jump to the marketplace, portfolio and statement.
- Platform-wide stats are kept as a secondary strip.
- Top-right **investor switcher** lets you view the app as any investor (demo, no password).

---

<p class="eyebrow">Investor app · Marketplace</p>

## Browse fundable invoices

![Marketplace listings](img/en-08-marketplace.png)

- Every open, fundable invoice is a card: debtor, sector, risk grade, amount and a live funding-progress bar.
- Each card shows the key economics — advance rate, fee per 30 days and estimated return — plus the target hold in days.
- The filter bar narrows by sector, risk grade, maximum term and minimum return.
- Click a card to open the full invoice detail.

---

<p class="eyebrow">Investor app · Invoice detail</p>

## Full transparency before you invest

![Invoice detail page](img/en-09-marketplace-detail.png)

- The headline shows the debtor, risk grade, sector and invoice number.
- A funding panel: amount raised vs goal, advance rate, fee and estimated return.
- A **debtor-company profile** lists registration number, sector, country and annual turnover.
- Everything needed to make a funding decision on a single screen.

---

<p class="eyebrow">Investor app · Portfolio</p>

## The reporting cockpit

![Portfolio cockpit](img/en-10-portfolio.png)

- Two hero panels: **net annual return** (interest received, write-offs, net income) and **account value** (active invested, expected outstanding, realized).
- An **investments aging table** buckets active positions by days to / past due.
- A **payment-habits table** shows how settled invoices actually paid — early, on time, late or written off.
- A positions table lists every investment with realized return, settlement date, grade and status.

---

<p class="eyebrow">Investor app · Account statement</p>

## Every transaction, filterable

![Account statement](img/en-11-statement.png)

- A unified ledger of cash movements: investments out (−) and settlements in (+).
- Filter by date range, type, counterparty, invoice number and minimum amount.
- Signed amounts in UZS, newest first.
- One-click **CSV export** for bookkeeping and reconciliation.

---

<p class="eyebrow">Investor app · Auto-invest</p>

## Set rules, invest automatically

![Auto-invest settings](img/en-12-auto-invest.png)

- Configure automated bidding: minimum risk grade, maximum amount per invoice and preferred sectors.
- Toggle the strategy active/inactive; the status is shown at the top.
- Rules are saved per investor and applied to matching new invoices.
- Modelled on investly.co's autobidder.

---

<p class="eyebrow">Supplier app · AI origination</p>

## From invoice document to financing demand

![AI invoice upload and extraction](img/en-19-invoice-upload.png)

- Upload a PDF, PNG, JPEG, JSON or text invoice; three synthetic PDF samples are included for a safe demonstration.
- Digital PDFs are converted to Markdown locally; only scanned/image-only invoices use the slower xAI vision fallback. Grok then extracts identities, dates, amount/currency, PO, tax/registration and bank details.
- Every result includes confidence, evidence and review issues; the supplier reviews editable JSON before submission.
- Submission creates the invoice and an open marketplace financing demand atomically, using the requested or default advance rate.

---

<p class="eyebrow">AI · Application triage</p>

## Chat-based invoice triage

![AI triage assistant](img/en-13-ai-triage.png)

- Sellers describe an invoice and debtor in plain language; the assistant collects only what is still missing.
- It returns an **indicative risk band (A–D)**, an **advance rate** and the **documents the bank needs next** — in seconds, not days.
- Powered by **Grok (x.ai)**; everything is indicative and subject to verification — no final decision is automated.
- Fully trilingual — the assistant replies in the visitor's language (English, Oʻzbekcha, Russian).

---

<p class="eyebrow">AI · Portfolio reporting</p>

## Ask your portfolio anything

![AI reporting assistant](img/en-14-ai-assistant.png)

- Investors ask questions in natural language — net return, exposure by sector or debtor, overdue positions, upcoming settlements.
- Answers are **grounded in the investor's own live positions** — every figure traces back to real portfolio data, not invented.
- Concrete and specific: it quotes actual amounts and invoice numbers, and says so plainly when the data can't answer.
- The conversational layer on top of the portfolio cockpit — reporting on demand, in the investor's language.

---

<p class="eyebrow">Get started</p>

## Start with Factorio

- **Sellers** — submit an invoice and get an offer in 1–3 working days.
- **Investors** — browse the marketplace, build a portfolio, automate with auto-invest.
- Live at **factorio.co.uk** · hello@factorio.co.uk
