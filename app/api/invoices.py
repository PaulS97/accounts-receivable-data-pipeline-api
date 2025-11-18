# app/api/invoices.py

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, select
from zoneinfo import ZoneInfo

from app.db.engine import get_engine
from app.db.schema import invoices, customers
from app.models.invoices import (
    InvoiceOut,
    MonthlySummaryOut,
    PastDueInvoiceItem,
    PastDueResponse,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _row_to_invoice(row) -> InvoiceOut:
    return InvoiceOut(
        id=row["id"],
        invoice_number=row["invoice_number"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        invoice_date=row["invoice_date"],
        due_date=row["due_date"],
        customer_po_number=row["customer_po_number"],
        bill_total=row["bill_total"],
        applied=row["applied"],
        status=row["status"],
        currency=row["currency"],
        customer_terms=row["customer_terms"],
        terms_days=row["terms_days"],
    )


@router.get("/past-due", response_model=PastDueResponse)
def list_past_due_invoices(
    as_of: Optional[date] = Query(
        default=None,
        description="ISO date (YYYY-MM-DD); defaults to server 'today' in America/New_York",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query(
        default="due_date.asc",
        description="due_date.asc | due_date.desc",
    ),
) -> PastDueResponse:
    """
    Returns invoices with positive outstanding balance whose DueDate is before as_of.
    """
    # Resolve as_of in America/New_York
    if as_of is None:
        as_of = datetime.now(ZoneInfo("America/New_York")).date()

    # Sorting
    if sort == "due_date.desc":
        order_clause = invoices.c.due_date.desc()
    else:
        order_clause = invoices.c.due_date.asc()

    engine = get_engine()

    with engine.connect() as conn:
        # Base filter: outstanding > 0 AND due_date < as_of
        outstanding_expr = (
            func.coalesce(invoices.c.bill_total, 0)
            - func.coalesce(invoices.c.applied, 0)
        )

        base_where = and_(
            outstanding_expr > 0,
            invoices.c.due_date < as_of,
        )

        # Total count (before limit/offset)
        count_stmt = select(func.count()).where(base_where)
        total = conn.execute(count_stmt).scalar_one()

        # Paged query
        stmt = (
            select(
                invoices.c.invoice_number,
                customers.c.name.label("customer_name"),
                invoices.c.invoice_date,
                invoices.c.due_date,
                invoices.c.bill_total,
                invoices.c.applied,
                invoices.c.currency,
                invoices.c.status,
            )
            .select_from(invoices.join(customers))
            .where(base_where)
            .order_by(order_clause)
            .limit(limit)
            .offset(offset)
        )

        rows = conn.execute(stmt).mappings().all()

    items: List[PastDueInvoiceItem] = []
    zero = Decimal("0")

    for row in rows:
        bill_total = row["bill_total"] or zero
        applied = row["applied"] or zero
        raw_outstanding = bill_total - applied
        outstanding = raw_outstanding if raw_outstanding > zero else zero

        # days_past_due = (as_of - due_date).days
        days_past_due = (as_of - row["due_date"]).days

        items.append(
            PastDueInvoiceItem(
                invoice_number=row["invoice_number"],
                customer_name=row["customer_name"],
                invoice_date=row["invoice_date"],
                due_date=row["due_date"],
                bill_total=bill_total,
                applied=applied,
                outstanding=outstanding,
                currency=row["currency"],
                status=row["status"],
                days_past_due=days_past_due,
            )
        )

    return PastDueResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{invoice_number}", response_model=InvoiceOut)
def get_invoice(invoice_number: str) -> InvoiceOut:
    """
    Look up a single invoice by its invoice_number.
    """
    engine = get_engine()

    with engine.connect() as conn:
        stmt = (
            select(
                invoices.c.id,
                invoices.c.invoice_number,
                invoices.c.customer_id,
                customers.c.name.label("customer_name"),
                invoices.c.invoice_date,
                invoices.c.due_date,
                invoices.c.customer_po_number,
                invoices.c.bill_total,
                invoices.c.applied,
                invoices.c.status,
                invoices.c.currency,
                invoices.c.customer_terms,
                invoices.c.terms_days,
            )
            .select_from(invoices.join(customers))
            .where(invoices.c.invoice_number == invoice_number)
        )

        row = conn.execute(stmt).mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return _row_to_invoice(row)

@router.get("/summary/month", response_model=MonthlySummaryOut)
def monthly_summary(
    month: str = Query(..., description="Target month in YYYY-MM format"),
    customer_name: Optional[str] = Query(
        default=None,
        description="Optional customer name, case-insensitive exact match",
    ),
) -> MonthlySummaryOut:
    """
    Returns the sum of BillTotal for invoices whose InvoiceDate falls in the target month,
    optionally filtered by customer_name (case-insensitive exact match).
    """
    # Parse month
    try:
        dt = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format")

    year, m = dt.year, dt.month
    first_day = date(year, m, 1)
    next_month = date(year + (m == 12), (m % 12) + 1, 1)

    engine = get_engine()
    with engine.connect() as conn:
        # Base filter on invoice_date range
        conditions = [
            invoices.c.invoice_date >= first_day,
            invoices.c.invoice_date < next_month,
        ]

        # Optional customer_name filter (case-insensitive)
        if customer_name is not None:
            conditions.append(
                func.lower(customers.c.name) == func.lower(customer_name)
            )

        stmt = (
            select(
                func.coalesce(func.sum(invoices.c.bill_total), 0).label("sum_bill_total"),
                func.count().label("count_invoices"),
                func.coalesce(func.min(invoices.c.currency), "USD").label("currency"),
            )
            .select_from(invoices.join(customers))
            .where(and_(*conditions))
        )

        row = conn.execute(stmt).first()

    sum_bill_total = row.sum_bill_total or Decimal("0")
    count_invoices = row.count_invoices or 0
    currency = row.currency or "USD"

    return MonthlySummaryOut(
        month=month,
        currency=currency,
        sum_bill_total=sum_bill_total,
        count_invoices=count_invoices,
    )
