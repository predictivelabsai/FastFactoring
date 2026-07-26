-- FactorFinance schema — invoice financing platform
-- All tables live in the factorio.* schema.

CREATE SCHEMA IF NOT EXISTS factorio;

-- ── Users ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    username    TEXT NOT NULL DEFAULT '',
    role        TEXT NOT NULL DEFAULT 'investor' CHECK (role IN ('investor', 'seller', 'admin')),
    phone       TEXT NOT NULL DEFAULT '',
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Companies (seller businesses) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.companies (
    id                  BIGSERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    registration_number TEXT UNIQUE NOT NULL,
    sector              TEXT NOT NULL DEFAULT 'other',
    country             TEXT NOT NULL DEFAULT 'EE',
    address             TEXT NOT NULL DEFAULT '',
    annual_turnover     NUMERIC(15,2) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS companies_sector_idx ON factorio.companies(sector);

-- ── Invoices (core financeable asset) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.invoices (
    id                      BIGSERIAL PRIMARY KEY,
    invoice_number          TEXT UNIQUE NOT NULL,
    seller_id               BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    company_id              BIGINT NOT NULL REFERENCES factorio.companies(id) ON DELETE CASCADE,
    debtor_name             TEXT NOT NULL,
    debtor_registration     TEXT NOT NULL DEFAULT '',
    description             TEXT NOT NULL DEFAULT '',
    sector                  TEXT NOT NULL DEFAULT 'other',
    amount                  NUMERIC(15,2) NOT NULL,
    currency                TEXT NOT NULL DEFAULT 'EUR',
    issue_date              DATE NOT NULL,
    due_date                DATE NOT NULL,
    payment_terms_days      INT NOT NULL DEFAULT 30,
    status                  TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'verified', 'funding', 'funded', 'settled', 'defaulted', 'cancelled')),
    risk_grade              TEXT NOT NULL DEFAULT 'B' CHECK (risk_grade IN ('A', 'B', 'C', 'D')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS invoices_status_idx ON factorio.invoices(status);
CREATE INDEX IF NOT EXISTS invoices_seller_idx ON factorio.invoices(seller_id);
CREATE INDEX IF NOT EXISTS invoices_company_idx ON factorio.invoices(company_id);
CREATE INDEX IF NOT EXISTS invoices_due_date_idx ON factorio.invoices(due_date);

-- Extracted payment/origination metadata (nullable for legacy seeded invoices).
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_name TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_registration TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_tax_id TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_bank_name TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_bank_account TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_iban TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS supplier_swift TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS purchase_order_number TEXT NOT NULL DEFAULT '';
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS extraction_confidence NUMERIC(5,2);
ALTER TABLE factorio.invoices ADD COLUMN IF NOT EXISTS extraction_evidence TEXT NOT NULL DEFAULT '';

-- ── Invoice Funding (funding round per invoice) ────────────────────────
CREATE TABLE IF NOT EXISTS factorio.invoice_funding (
    id                          BIGSERIAL PRIMARY KEY,
    invoice_id                  BIGINT NOT NULL REFERENCES factorio.invoices(id) ON DELETE CASCADE,
    name                        TEXT NOT NULL,
    description                 TEXT NOT NULL DEFAULT '',
    funding_goal                NUMERIC(15,2) NOT NULL,
    amount_raised               NUMERIC(15,2) NOT NULL DEFAULT 0,
    minimum_investment          NUMERIC(15,2) NOT NULL DEFAULT 50,
    advance_rate_pct            NUMERIC(5,2) NOT NULL DEFAULT 85.00,
    fee_pct_per_30d             NUMERIC(5,2) NOT NULL DEFAULT 2.00,
    estimated_return_pct        NUMERIC(5,2) NOT NULL DEFAULT 8.00,
    risk_grade                  TEXT NOT NULL DEFAULT 'B',
    funding_status              TEXT NOT NULL DEFAULT 'open' CHECK (funding_status IN ('open', 'closed', 'funded', 'settled', 'defaulted')),
    start_date                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    end_date                    TIMESTAMPTZ,
    target_hold_days            INT NOT NULL DEFAULT 30,
    show_in_marketplace         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS funding_invoice_idx ON factorio.invoice_funding(invoice_id);
CREATE INDEX IF NOT EXISTS funding_status_idx ON factorio.invoice_funding(funding_status);

-- ── Investments (investor ↔ funding link) ──────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.investments (
    id                      BIGSERIAL PRIMARY KEY,
    funding_id              BIGINT NOT NULL REFERENCES factorio.invoice_funding(id) ON DELETE CASCADE,
    investor_id             BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    investment_amount       NUMERIC(15,2) NOT NULL,
    ownership_pct           NUMERIC(5,2) NOT NULL DEFAULT 0,
    expected_return_amount  NUMERIC(15,2) NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'settled', 'defaulted')),
    investment_date         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (funding_id, investor_id)
);
CREATE INDEX IF NOT EXISTS investments_investor_idx ON factorio.investments(investor_id);

-- ── Invoice Updates (status timeline) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.invoice_updates (
    id          BIGSERIAL PRIMARY KEY,
    invoice_id  BIGINT NOT NULL REFERENCES factorio.invoices(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    update_type TEXT NOT NULL DEFAULT 'status_update',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Notifications ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.notifications (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    type        TEXT NOT NULL DEFAULT 'general',
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    data_id     BIGINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON factorio.notifications(user_id);

-- ── Settlements (when debtor pays) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.settlements (
    id                  BIGSERIAL PRIMARY KEY,
    funding_id          BIGINT NOT NULL REFERENCES factorio.invoice_funding(id) ON DELETE CASCADE,
    settlement_amount   NUMERIC(15,2) NOT NULL,
    settlement_date     TIMESTAMPTZ NOT NULL,
    settlement_terms    TEXT NOT NULL DEFAULT '',
    is_approved         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Dividends (returns to investors) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.dividends (
    id              BIGSERIAL PRIMARY KEY,
    investor_id     BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    funding_id      BIGINT NOT NULL REFERENCES factorio.invoice_funding(id) ON DELETE CASCADE,
    amount          NUMERIC(15,2) NOT NULL,
    invested_amount NUMERIC(15,2) NOT NULL,
    is_paid         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Payments (investor payment records) ────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.payments (
    id                  BIGSERIAL PRIMARY KEY,
    investor_id         BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    investment_id       BIGINT NOT NULL REFERENCES factorio.investments(id) ON DELETE CASCADE,
    amount              NUMERIC(15,2) NOT NULL,
    payment_status      TEXT NOT NULL DEFAULT 'pending' CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded')),
    payment_date        TIMESTAMPTZ,
    transaction_id      TEXT UNIQUE NOT NULL,
    reference_number    TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);

-- ── Secondary Market ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.secondary_market (
    id              BIGSERIAL PRIMARY KEY,
    investor_id     BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    investment_id   BIGINT NOT NULL REFERENCES factorio.investments(id) ON DELETE CASCADE,
    listing_price   NUMERIC(15,2) NOT NULL,
    status          TEXT NOT NULL DEFAULT 'listed' CHECK (status IN ('listed', 'sold', 'cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Auto-Invest Preferences ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.auto_invest (
    id                  BIGSERIAL PRIMARY KEY,
    investor_id         BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    max_amount_per_invoice  NUMERIC(15,2) NOT NULL DEFAULT 500,
    min_risk_grade      TEXT NOT NULL DEFAULT 'B',
    preferred_sectors   TEXT NOT NULL DEFAULT '',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── FAQ ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.faq (
    id          BIGSERIAL PRIMARY KEY,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    sort_order  INT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Accounting / general ledger (back office) ──────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.gl_accounts (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK (type IN ('asset','liability','equity','income','expense'))
);

CREATE TABLE IF NOT EXISTS factorio.ledger_entries (
    id          BIGSERIAL PRIMARY KEY,
    entry_date  DATE NOT NULL,
    account_code TEXT NOT NULL REFERENCES factorio.gl_accounts(code),
    debit       NUMERIC(15,2) NOT NULL DEFAULT 0,
    credit      NUMERIC(15,2) NOT NULL DEFAULT 0,
    ref_type    TEXT NOT NULL DEFAULT '',
    ref_id      TEXT NOT NULL DEFAULT '',
    memo        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ledger_account_idx ON factorio.ledger_entries(account_code);

CREATE TABLE IF NOT EXISTS factorio.bank_transactions (
    id          BIGSERIAL PRIMARY KEY,
    txn_date    DATE NOT NULL,
    amount      NUMERIC(15,2) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    reconciled  BOOLEAN NOT NULL DEFAULT FALSE,
    ref_id      TEXT NOT NULL DEFAULT ''
);

-- ── Invoice processing / assignment (back office) ─────────────────────────
CREATE TABLE IF NOT EXISTS factorio.invoice_assignments (
    id BIGSERIAL PRIMARY KEY, invoice_id BIGINT UNIQUE, invoice_number TEXT NOT NULL,
    assignment_type TEXT NOT NULL DEFAULT 'notified', po_matched BOOLEAN NOT NULL DEFAULT FALSE,
    verified BOOLEAN NOT NULL DEFAULT FALSE, registered BOOLEAN NOT NULL DEFAULT FALSE,
    holdback NUMERIC(15,2) NOT NULL DEFAULT 0, reserve NUMERIC(15,2) NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'submitted', updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── App users / auth (back office) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.app_users (
    email TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '',
    salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'investor', subrole TEXT NOT NULL DEFAULT 'ops',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Collections (back office) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.collections_actions (
    id BIGSERIAL PRIMARY KEY, invoice_number TEXT NOT NULL, stage INT NOT NULL DEFAULT 0,
    action_type TEXT NOT NULL DEFAULT 'dunning', note TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Credit scoring (back office) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.credit_scores (
    id           BIGSERIAL PRIMARY KEY,
    subject      TEXT NOT NULL,
    score        NUMERIC(5,2) NOT NULL,
    grade        TEXT NOT NULL,
    pd_expected  NUMERIC(5,4) NOT NULL,
    advance_rate NUMERIC(5,2) NOT NULL,
    price_bps    INT NOT NULL,
    n_invoices   INT NOT NULL DEFAULT 0,
    observed_default NUMERIC(5,4),
    features     TEXT NOT NULL DEFAULT '',
    reasons      TEXT NOT NULL DEFAULT '',
    scored_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS factorio.integrations (
    name        TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    connected   BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Workspace modules (CRM / Drive / Docs / Mail) ─────────────────────────
CREATE TABLE IF NOT EXISTS factorio.crm_deals (
    id          BIGSERIAL PRIMARY KEY,
    client      TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    stage       TEXT NOT NULL,
    value       NUMERIC(15,2) NOT NULL DEFAULT 0,
    owner       TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS factorio.drive_files (
    id            BIGSERIAL PRIMARY KEY,
    icon          TEXT NOT NULL DEFAULT '📄',
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'file',
    size          TEXT NOT NULL DEFAULT '—',
    updated_label TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS factorio.workspace_docs (
    id        BIGSERIAL PRIMARY KEY,
    title     TEXT NOT NULL,
    folder    TEXT NOT NULL DEFAULT '',
    excerpt   TEXT NOT NULL DEFAULT '',
    words     INT NOT NULL DEFAULT 0,
    published BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS factorio.mail_messages (
    id         BIGSERIAL PRIMARY KEY,
    sender     TEXT NOT NULL,
    subject    TEXT NOT NULL DEFAULT '',
    snippet    TEXT NOT NULL DEFAULT '',
    when_label TEXT NOT NULL DEFAULT '',
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INT NOT NULL DEFAULT 0
);

-- ── Reverse-auction bids (marketplace depth) ──────────────────────────────
CREATE TABLE IF NOT EXISTS factorio.auction_bids (
    id              BIGSERIAL PRIMARY KEY,
    funding_id      BIGINT NOT NULL REFERENCES factorio.invoice_funding(id) ON DELETE CASCADE,
    investor_id     BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
    bid_fee_pct     NUMERIC(5,2) NOT NULL,
    bid_advance_pct NUMERIC(5,2) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Immutable public snapshots created from the browser-based Factorio AI chat.
CREATE TABLE IF NOT EXISTS factorio.shared_chats (
    token       TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'Factorio AI chat',
    messages    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
