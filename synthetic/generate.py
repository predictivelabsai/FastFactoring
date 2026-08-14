"""Deterministic synthetic data generator for FastFactoring.

Usage:
    python -m synthetic.generate                    # seed with default seed=42
    python -m synthetic.generate --seed 99          # custom seed
    python -m synthetic.generate --seed 42 --fresh  # truncate then re-seed
    python -m synthetic.generate --limit 5          # small subset
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from faker import Faker

from db import connect

SECTORS = ["manufacturing", "wholesale", "construction", "logistics", "services",
           "mining", "energy", "agriculture", "telecom", "finance"]
RISK_GRADES = ["A", "B", "B", "C"]  # weighted toward B
CURRENCIES = ["UZS"]
COUNTRIES = ["UZ"]

COMPANY_TEMPLATES = [
    ("Acme Distribution Co", "wholesale", "US"),
    ("Vertex Construction", "construction", "US"),
    ("Meridian Logistics", "logistics", "GB"),
    ("Greenfield Agro", "agriculture", "US"),
    ("Ironclad Manufacturing", "manufacturing", "DE"),
    ("Apex Machine Works", "manufacturing", "US"),
    ("Summit Freight", "logistics", "GB"),
    ("Helios Energy Services", "energy", "US"),
    ("Northwind IT Solutions", "services", "US"),
    ("Harvest Grain Co", "agriculture", "US"),
    ("Cornerstone Building Materials", "construction", "US"),
    ("Bright Textiles", "manufacturing", "GB"),
    ("Clarity Consulting", "services", "US"),
    ("Pioneer Trading", "wholesale", "US"),
    ("Catalyst Chemicals", "manufacturing", "DE"),
]

DEBTOR_NAMES = [
    "Globex Corporation", "Initech LLC", "Umbrella Industries", "Stark Industries",
    "Wayne Enterprises", "Wonka Industries", "Hooli Inc", "Cyberdyne Systems",
    "Soylent Corp", "Massive Dynamic", "Vandelay Industries", "Nakatomi Trading",
    "Tyrell Corp", "Oscorp Industries", "Prestige Worldwide", "Dunder Mifflin",
    "Sterling Cooper", "Aperture Science", "Weyland-Yutani", "Virtucon",
    "Zorg Industries", "Gekko & Co", "Monarch Holdings", "Pied Piper Inc",
    "Bluth Company",
]


def _truncate(conn) -> None:
    tables = [
        "dividends", "settlements", "payments", "secondary_market",
        "auto_invest", "investments", "invoice_updates", "notifications",
        "invoice_funding", "invoices", "faq", "companies", "users",
    ]
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"TRUNCATE factorio.{t} CASCADE")
    conn.commit()
    print("[synthetic] truncated all tables")


def _seed_users(conn, rng: random.Random, fake: Faker) -> dict[str, int]:
    users = []
    for role, count in [("admin", 2), ("seller", 10), ("investor", 20)]:
        for i in range(count):
            users.append({
                "email": f"{role}{i+1}@factorio.co.uk",
                "username": f"{role}{i+1}",
                "role": role,
                "phone": fake.phone_number(),
                "is_verified": True,
            })

    id_map = {}
    with conn.cursor() as cur:
        for u in users:
            cur.execute("""
                INSERT INTO factorio.users (email, username, role, phone, is_verified)
                VALUES (%(email)s, %(username)s, %(role)s, %(phone)s, %(is_verified)s)
                ON CONFLICT (email) DO UPDATE SET username = EXCLUDED.username
                RETURNING id, email
            """, u)
            row = cur.fetchone()
            id_map[row[1]] = row[0]
    conn.commit()
    print(f"[synthetic] seeded {len(users)} users")
    return id_map


def _seed_companies(conn, rng: random.Random, fake: Faker) -> dict[str, int]:
    id_map = {}
    with conn.cursor() as cur:
        for name, sector, country in COMPANY_TEMPLATES:
            reg = f"{country}{rng.randint(10000000, 99999999)}"
            # realistic annual turnover: ~$2.5M–$40M (UZS-scale, converted for display)
            turnover = rng.randint(30_000_000_000, 500_000_000_000)
            cur.execute("""
                INSERT INTO factorio.companies (name, registration_number, sector, country, address, annual_turnover)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (registration_number) DO UPDATE SET name = EXCLUDED.name
                RETURNING id, name
            """, (name, reg, sector, country, fake.address().replace("\n", ", "), turnover))
            row = cur.fetchone()
            id_map[row[1]] = row[0]
    conn.commit()
    print(f"[synthetic] seeded {len(COMPANY_TEMPLATES)} companies")
    return id_map


def _settlement_delay(rng: random.Random) -> int:
    """Days relative to the due date the debtor actually paid.

    Negative = paid early, 0 = on time, positive = late. Weighted toward
    on-time/early so the payment-habits table looks like a healthy book.
    """
    bucket = rng.choices(
        ["earlier", "on_time", "l1_14", "l15_30", "l31_60", "l61_120"],
        weights=[28, 40, 16, 8, 5, 3],
    )[0]
    return {
        "earlier": rng.randint(-15, -1),
        "on_time": 0,
        "l1_14": rng.randint(1, 14),
        "l15_30": rng.randint(15, 30),
        "l31_60": rng.randint(31, 60),
        "l61_120": rng.randint(61, 120),
    }[bucket]


def _seed_invoices_and_funding(
    conn, rng: random.Random, fake: Faker,
    user_ids: dict[str, int], company_ids: dict[str, int],
    limit: int | None = None,
) -> None:
    seller_emails = [e for e in user_ids if e.startswith("seller")]
    investor_emails = [e for e in user_ids if e.startswith("investor")]
    company_names = list(company_ids.keys())
    today = date.today()

    invoice_count = limit or 30
    counts = {"invoices": 0, "fundings": 0, "investments": 0,
              "settlements": 0, "dividends": 0, "payments": 0,
              "updates": 0, "notifications": 0}

    def _add_update(cur, invoice_id, title, utype, when):
        cur.execute("""
            INSERT INTO factorio.invoice_updates
                (invoice_id, title, description, update_type, created_at)
            VALUES (%s,%s,%s,%s,%s)
        """, (invoice_id, title, "", utype, when))
        counts["updates"] += 1

    def _notify(cur, user_id, title, message, ntype, data_id, when):
        cur.execute("""
            INSERT INTO factorio.notifications
                (user_id, title, message, type, is_read, data_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, title, message, ntype, rng.random() < 0.5, data_id, when))
        counts["notifications"] += 1

    with conn.cursor() as cur:
        for i in range(invoice_count):
            seller_email = rng.choice(seller_emails)
            seller_id = user_ids[seller_email]
            company_name = rng.choice(company_names)
            company_id = company_ids[company_name]
            debtor = rng.choice(DEBTOR_NAMES)
            sector = rng.choice(SECTORS)
            amount = round(rng.uniform(50_000_000, 3_000_000_000), 2)
            terms = rng.choice([15, 30, 45, 60, 90, 120, 180])
            issue_date = today - timedelta(days=rng.randint(5, 150))
            due_date = issue_date + timedelta(days=terms)
            risk = rng.choice(RISK_GRADES)
            status = rng.choices(
                ["verified", "funding", "funding", "funded", "settled", "defaulted"],
                weights=[10, 20, 20, 20, 25, 5],
            )[0]
            inv_num = f"INV-{2026}{i+1:04d}"
            funding_date = issue_date + timedelta(days=rng.randint(1, 5))

            cur.execute("""
                INSERT INTO factorio.invoices
                    (invoice_number, seller_id, company_id, debtor_name,
                     debtor_registration, description, sector, amount, currency,
                     issue_date, due_date, payment_terms_days, status, risk_grade)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (invoice_number) DO UPDATE SET status = EXCLUDED.status
                RETURNING id
            """, (inv_num, seller_id, company_id, debtor,
                  f"REG{rng.randint(10000,99999)}", fake.sentence(),
                  sector, amount, "UZS", issue_date, due_date, terms, status, risk))
            invoice_id = cur.fetchone()[0]
            counts["invoices"] += 1

            # ── Status timeline (invoice_updates) ──────────────────────
            _add_update(cur, invoice_id, "Invoice submitted", "created", issue_date)
            _add_update(cur, invoice_id, "Invoice verified", "verified",
                        issue_date + timedelta(days=1))

            if status in ("funding", "funded", "settled", "defaulted"):
                advance_rate = round(rng.uniform(80, 92), 2)
                fee = round(rng.uniform(1.0, 3.5), 2)
                goal = round(amount * advance_rate / 100, 2)
                raised = goal if status in ("funded", "settled", "defaulted") \
                    else round(goal * rng.uniform(0.1, 0.9), 2)
                est_return = round(fee * terms / 30, 2)
                f_status = {"funding": "open", "funded": "funded",
                            "settled": "settled", "defaulted": "defaulted"}[status]

                cur.execute("""
                    INSERT INTO factorio.invoice_funding
                        (invoice_id, name, description, funding_goal, amount_raised,
                         minimum_investment, advance_rate_pct, fee_pct_per_30d,
                         estimated_return_pct, risk_grade, funding_status,
                         target_hold_days, show_in_marketplace, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (invoice_id, f"{debtor} — {inv_num}", fake.sentence(),
                      goal, raised, 500_000, advance_rate, fee, est_return, risk,
                      f_status, terms, f_status == "open", funding_date))
                funding_id = cur.fetchone()[0]
                counts["fundings"] += 1
                _add_update(cur, invoice_id, "Funding round opened", "funding", funding_date)
                if status in ("funded", "settled", "defaulted"):
                    _add_update(cur, invoice_id, "Fully funded", "funded",
                                funding_date + timedelta(days=rng.randint(1, 4)))

                settlement_date = None
                if status == "settled":
                    settlement_date = due_date + timedelta(days=_settlement_delay(rng))

                num_investors = rng.randint(1, 5)
                chosen = rng.sample(investor_emails, min(num_investors, len(investor_emails)))
                for inv_email in chosen:
                    investor_id = user_ids[inv_email]
                    inv_amount = round(raised / len(chosen), 2)
                    own_pct = round(inv_amount / goal * 100, 2) if goal else 0
                    exp_return = round(inv_amount * (1 + est_return / 100), 2)
                    inv_status = {"settled": "settled", "defaulted": "defaulted"}.get(status, "confirmed")

                    cur.execute("""
                        INSERT INTO factorio.investments
                            (funding_id, investor_id, investment_amount, ownership_pct,
                             expected_return_amount, status, investment_date)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (funding_id, investor_id) DO UPDATE
                            SET investment_amount = EXCLUDED.investment_amount,
                                status = EXCLUDED.status
                        RETURNING id
                    """, (funding_id, investor_id, inv_amount, own_pct,
                          exp_return, inv_status, funding_date))
                    investment_id = cur.fetchone()[0]
                    counts["investments"] += 1

                    # Outbound payment record for the investment itself.
                    cur.execute("""
                        INSERT INTO factorio.payments
                            (investor_id, investment_id, amount, payment_status,
                             payment_date, transaction_id, reference_number, completed_at)
                        VALUES (%s,%s,%s,'completed',%s,%s,%s,%s)
                        ON CONFLICT (transaction_id) DO NOTHING
                    """, (investor_id, investment_id, inv_amount, funding_date,
                          f"TXN-{funding_id}-{investor_id}", f"REF-{inv_num}", funding_date))
                    counts["payments"] += 1

                    if status == "settled":
                        interest = round(exp_return - inv_amount, 2)
                        cur.execute("""
                            INSERT INTO factorio.dividends
                                (investor_id, funding_id, amount, invested_amount, is_paid, created_at)
                            VALUES (%s,%s,%s,%s,TRUE,%s)
                        """, (investor_id, funding_id, interest, inv_amount, settlement_date))
                        counts["dividends"] += 1
                        _notify(cur, investor_id, "Dividend received",
                                f"Invoice {inv_num} settled — returns paid.",
                                "dividend", funding_id, settlement_date)
                    elif status == "defaulted":
                        _notify(cur, investor_id, "Invoice defaulted",
                                f"Invoice {inv_num} was written off.",
                                "default", funding_id, due_date + timedelta(days=30))
                    else:
                        _notify(cur, investor_id, "Investment confirmed",
                                f"Your investment in {inv_num} is confirmed.",
                                "investment", funding_id, funding_date)

                if status == "settled":
                    cur.execute("""
                        INSERT INTO factorio.settlements
                            (funding_id, settlement_amount, settlement_date,
                             settlement_terms, is_approved)
                        VALUES (%s,%s,%s,%s,TRUE)
                    """, (funding_id, raised, settlement_date, "Paid in full by debtor"))
                    counts["settlements"] += 1
                    _add_update(cur, invoice_id, "Payment received — settled",
                                "settled", settlement_date)
                elif status == "defaulted":
                    _add_update(cur, invoice_id, "Marked as defaulted", "defaulted",
                                due_date + timedelta(days=30))

    conn.commit()
    print("[synthetic] seeded "
          + ", ".join(f"{v} {k}" for k, v in counts.items()))


def _seed_auto_invest(conn, rng: random.Random, user_ids: dict[str, int]) -> None:
    investor_ids = [uid for email, uid in user_ids.items() if email.startswith("investor")]
    created = 0
    with conn.cursor() as cur:
        for investor_id in investor_ids:
            if rng.random() < 0.4:  # only some investors have configured rules
                continue
            sectors = rng.sample(SECTORS, rng.randint(0, 3))
            cur.execute("DELETE FROM factorio.auto_invest WHERE investor_id = %s",
                        (investor_id,))
            cur.execute("""
                INSERT INTO factorio.auto_invest
                    (investor_id, max_amount_per_invoice, min_risk_grade,
                     preferred_sectors, is_active)
                VALUES (%s,%s,%s,%s,%s)
            """, (investor_id,
                  rng.choice([1_000_000, 2_000_000, 5_000_000, 10_000_000]),
                  rng.choice(["A", "B", "B", "C"]),
                  ",".join(sectors),
                  rng.random() < 0.6))
            created += 1
    conn.commit()
    print(f"[synthetic] seeded {created} auto-invest rules")


def _seed_faq(conn) -> None:
    faqs = [
        ("What is invoice financing?", "Invoice financing (also called factoring) lets you sell your unpaid invoices to investors at a discount. You get cash immediately; investors earn a return when the debtor pays."),
        ("How quickly can I get funded?", "Once your invoice is verified (typically 24 hours), it's listed on our marketplace. Most invoices are fully funded within 1-3 business days."),
        ("What fees does Factorio charge?", "Sellers pay a fee of 1.5-3% per 30 days, depending on invoice size, debtor credit quality, and payment terms. There are no setup fees or monthly minimums."),
        ("What's the minimum investment?", "You can invest from 500,000 UZS per invoice, making it easy to diversify across multiple invoices, sectors, and risk grades."),
        ("How are invoices risk-graded?", "We assess each invoice on debtor creditworthiness, payment history, seller track record, and sector risk. Grades range from A (lowest risk) to D (highest risk)."),
        ("What happens if the debtor doesn't pay?", "We have a collections process in place. For defaulted invoices, we work with the seller and, if necessary, third-party collection agencies. Investors bear the risk of non-payment."),
    ]
    with conn.cursor() as cur:
        for i, (q, a) in enumerate(faqs):
            cur.execute("""
                INSERT INTO factorio.faq (question, answer, sort_order, is_active)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT DO NOTHING
            """, (q, a, i))
    conn.commit()
    print(f"[synthetic] seeded {len(faqs)} FAQs")


def run(seed: int = 42, fresh: bool = False, limit: int | None = None) -> None:
    rng = random.Random(seed)
    fake = Faker()
    Faker.seed(seed)

    with connect() as conn:
        if fresh:
            _truncate(conn)

        user_ids = _seed_users(conn, rng, fake)
        company_ids = _seed_companies(conn, rng, fake)
        _seed_invoices_and_funding(conn, rng, fake, user_ids, company_ids, limit=limit)
        _seed_auto_invest(conn, rng, user_ids)
        _seed_faq(conn)

    print("[synthetic] done")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic data for FastFactoring")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fresh", action="store_true", help="Truncate before seeding")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of invoices")
    args = parser.parse_args()
    run(seed=args.seed, fresh=args.fresh, limit=args.limit)


if __name__ == "__main__":
    main()
