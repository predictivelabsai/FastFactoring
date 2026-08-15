# Role-Based Access Control

FastFactoring has four persisted roles: `admin`, `supplier`, `investor`, and
`payer`. “Supplier” includes the borrower workflow. Public registration and
Google sign-in may create any non-admin role; only `kaljuvee@gmail.com` can hold
`admin`.

Authentication and authorization are separate. The signed session contains the
account identity, while every `/app` request reloads its access profile and
record scope from PostgreSQL. A hidden navigation item is never treated as an
authorization control.

## Role scope

- Supplier: its linked company, invoices, applications, and contracts.
- Investor: approved marketplace data and its own investments and portfolio.
- Payer: invoices matching its linked debtor registration number.
- Admin: all operational, settings, user, and audit views.

Governance → Team lets the admin invite users, change non-admin roles, and link
a payer company number. Admin rights cannot be invited or self-assigned.

## Admin preview

The top-right **Viewing as** selector changes only the effective role. It keeps
the signed-in admin identity and uses fixed synthetic Supplier, Investor, or
Payer scopes. A visible banner identifies preview mode. Preview actions are
audited, cannot access admin routes, and may mutate only synthetic scenario data;
real payouts, messages, webhooks, and non-demo records remain blocked.

## Acceptance scenarios

1. Google admin login, enter Supplier preview, receive 403 on an admin URL, then
   exit preview with the stored admin role unchanged.
2. Register and verify each public role; request a generic password-reset email;
   reject used, expired, and invalid tokens.
3. Supplier uploads an invoice and can read its application but not another
   supplier’s contract.
4. Admin reviews and advances an application; the supplier sees the new status.
5. Investor can invest and read only its own position despite cookie/URL changes.
6. Payer sees only obligations for its linked registration and cannot confirm a
   different debtor’s invoice.
7. A synthetic settlement is visible to each role only through its own scope.
8. Anonymous requests redirect to login; preview and Team mutations require
   CSRF; demotion takes effect on the next request; denials are audited.
