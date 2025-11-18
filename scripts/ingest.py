# scripts/ingest.py

import csv
from decimal import Decimal
from datetime import datetime, timedelta
import re

from app.db.engine import get_engine
from app.db.schema import customers, invoices
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

FILE_PATH = "data/unicorn_inc.csv"


# ---- Helpers ----

def parse_money(value: str) -> Decimal:
    value = value.strip()
    if value == "":
        return Decimal("0")
    return Decimal(value)


def parse_invoice_date(value: str):
    value = value.strip()
    if not value:
        return None
    value = value.split()[0]
    return datetime.strptime(value, "%m/%d/%y").date()


def parse_due_date_raw(value: str):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    value = value.split()[0]
    return datetime.strptime(value, "%m/%d/%y").date()


def extract_terms_days(terms: str):
    if terms is None:
        return None
    terms = terms.strip()
    if not terms:
        return None
    m = re.search(r"(\d+)", terms)
    if not m:
        return None
    return int(m.group(1))


def upsert_invoice(conn, invoice_row: dict) -> None:
    """
    Insert or update an invoice by InvoiceNumber (idempotent ingest).

    invoice_row: dict mapping column names to values, e.g.
      {
        "invoice_number": "...",
        "customer_id": 1,
        "invoice_date": date(...),
        "due_date": date(...),
        "customer_po_number": "...",
        "bill_total": Decimal("..."),
        "applied": Decimal("..."),
        "status": "...",
        "currency": "USD",
        "customer_terms": "Net 30",
        "terms_days": 30,
      }
    """
    stmt = sqlite_insert(invoices).values(**invoice_row)

    # On conflict by invoice_number, update the mutable fields
    update_cols = {
        "customer_id": stmt.excluded.customer_id,
        "invoice_date": stmt.excluded.invoice_date,
        "due_date": stmt.excluded.due_date,
        "customer_po_number": stmt.excluded.customer_po_number,
        "bill_total": stmt.excluded.bill_total,
        "applied": stmt.excluded.applied,
        "status": stmt.excluded.status,
        "currency": stmt.excluded.currency,
        "customer_terms": stmt.excluded.customer_terms,
        "terms_days": stmt.excluded.terms_days,
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=[invoices.c.invoice_number],
        set_=update_cols,
    )

    conn.execute(stmt)


def parse_unicorn_csv(file_path: str = FILE_PATH):
    customers_by_name = {}
    invoices_list = []
    next_customer_id = 1

    n_rows = 0
    n_errors = 0
    error_examples = []

    # NEW: duplicate invoice tracking
    seen_invoice_numbers: set[str] = set()
    duplicate_invoice_examples: list[str] = []
    duplicate_invoice_count = 0

    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            n_rows += 1

            try:
                # ----- CUSTOMER HANDLING -----
                cname = row["CustomerName"].strip()

                if cname not in customers_by_name:
                    customers_by_name[cname] = {
                        "customer_id": next_customer_id,
                        "name": cname,
                        "contact_name": row["ContactName"].strip() if row["ContactName"] else None,
                        "contact_phone": row["ContactPhone"].strip() if row["ContactPhone"] else None,
                        "contact_email": row["ContactEmail"].strip() if row["ContactEmail"] else None,
                    }
                    next_customer_id += 1
                else:
                    cust = customers_by_name[cname]
                    if not cust["contact_name"] and row["ContactName"]:
                        cust["contact_name"] = row["ContactName"].strip()
                    if not cust["contact_phone"] and row["ContactPhone"]:
                        cust["contact_phone"] = row["ContactPhone"].strip()
                    if not cust["contact_email"] and row["ContactEmail"]:
                        cust["contact_email"] = row["ContactEmail"].strip()

                customer_id = customers_by_name[cname]["customer_id"]

                # ----- MONEY -----
                bill_total = parse_money(row["BillTotal"])
                applied = parse_money(row["Applied"])

                # ----- DATES -----
                invoice_date = parse_invoice_date(row["InvoiceDate"])
                terms_days = extract_terms_days(row["CustomerTerms"])
                due_date = parse_due_date_raw(row["DueDate"])

                if due_date is None and invoice_date is not None and terms_days is not None:
                    due_date = invoice_date + timedelta(days=terms_days)

                # ----- INVOICE RECORD -----
                invoice_record = {
                    "invoice_number": row["InvoiceNumber"].strip(),
                    "customer_id": customer_id,
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "customer_po_number": row["CustomerPoNumber"].strip(),
                    "bill_total": bill_total,
                    "applied": applied,
                    "status": row["Status"].strip() if row["Status"] else None,
                    "currency": row["Currency"].strip() if row["Currency"] else None,
                    "customer_terms": row["CustomerTerms"].strip() if row["CustomerTerms"] else None,
                    "terms_days": terms_days,
                }

                invoices_list.append(invoice_record)

                invoice_number = row["InvoiceNumber"].strip()

                # NEW: duplicate detection
                if invoice_number in seen_invoice_numbers:
                    duplicate_invoice_count += 1
                    if len(duplicate_invoice_examples) < 5:
                        duplicate_invoice_examples.append(
                            f"Duplicate InvoiceNumber {invoice_number!r} at CSV row {n_rows}"
                        )
                else:
                    seen_invoice_numbers.add(invoice_number)



            except Exception as e:
                n_errors += 1
                if len(error_examples) < 5:
                    error_examples.append(
                        {
                            "row_number": n_rows,
                            "row": dict(row),
                            "error": repr(e),
                        }
                    )

    customers_list = list(customers_by_name.values())

    stats = {
        "n_rows": n_rows,
        "n_customers": len(customers_by_name),
        "n_invoices": len(invoices_list),
        "n_errors": n_errors,
        "error_examples": error_examples,
        # NEW
        "n_duplicate_invoices": duplicate_invoice_count,
        "duplicate_invoice_examples": duplicate_invoice_examples,
    }
    return customers_list, invoices_list, stats



def load_into_db(customers_list, invoices_list):
    engine = get_engine()
    with engine.begin() as conn:
        # Rebuild customers from scratch (deterministic)
        conn.execute(customers.delete())

        conn.execute(
            customers.insert(),
            [
                {
                    "id": c["customer_id"],
                    "name": c["name"],
                    "contact_name": c["contact_name"],
                    "contact_phone": c["contact_phone"],
                    "contact_email": c["contact_email"],
                }
                for c in customers_list
            ],
        )

        # Idempotent invoices: upsert by invoice_number
        for inv in invoices_list:
            upsert_invoice(conn, inv)


def main():
    customers_list, invoices_list, stats = parse_unicorn_csv(FILE_PATH)
    load_into_db(customers_list, invoices_list)

    logger.info(f"Total CSV rows read:   {stats['n_rows']}")
    logger.info(f"Unique customers:      {stats['n_customers']}")
    logger.info(f"Invoices parsed:       {stats['n_invoices']}")
    logger.info(f"Rows with errors:      {stats['n_errors']}")
    logger.info(
        "Duplicate invoices (by InvoiceNumber): %s",
        stats["n_duplicate_invoices"],
    )
    for example in stats["duplicate_invoice_examples"]:
        logger.warning("Duplicate invoice example: %s", example)


    if stats["error_examples"]:
        logger.warning("Example errors:")
        for ex in stats["error_examples"]:
            logger.warning("Row %s: %s", ex["row_number"], ex["error"])


if __name__ == "__main__":
    main()
