# app/api/customers.py

from typing import List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db.engine import get_engine
from app.db.schema import customers, invoices
from app.models.customers import (
    CustomerOut,
    ContactInfo,
    CustomerContactResponse,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=List[CustomerOut])
def list_customers() -> List[CustomerOut]:
    """
    Return all customers with their contact info.
    """
    engine = get_engine()

    with engine.connect() as conn:
        stmt = (
            select(
                customers.c.id,
                customers.c.name,
                customers.c.contact_name,
                customers.c.contact_phone,
                customers.c.contact_email,
            )
            .order_by(customers.c.name)
        )

        rows = conn.execute(stmt).mappings().all()

    return [
        CustomerOut(
            id=row["id"],
            name=row["name"],
            contact_name=row["contact_name"],
            contact_phone=row["contact_phone"],
            contact_email=row["contact_email"],
        )
        for row in rows
    ]


@router.get("/contact", response_model=CustomerContactResponse)
def get_customer_contact(
    name: str = Query(..., description="Customer name (case-insensitive exact match)"),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0),
) -> CustomerContactResponse:
    """
    Fetches contact info by customer name (case-insensitive), with last_seen_invoice_date.
    """
    engine = get_engine()

    with engine.connect() as conn:
        # Count matching customers (for total)
        count_stmt = (
            select(func.count())
            .select_from(customers)
            .where(func.lower(customers.c.name) == func.lower(name))
        )
        total_customers = conn.execute(count_stmt).scalar_one()

        if total_customers == 0:
            # Spec allows 404 if zero matches
            raise HTTPException(status_code=404, detail="Customer not found")

        # Fetch contacts + last_seen_invoice_date
        stmt = (
            select(
                customers.c.name.label("customer_name"),
                customers.c.contact_name,
                customers.c.contact_email,
                customers.c.contact_phone,
                func.max(invoices.c.invoice_date).label("last_seen_invoice_date"),
            )
            .select_from(customers.outerjoin(invoices))
            .where(func.lower(customers.c.name) == func.lower(name))
            .group_by(
                customers.c.id,
                customers.c.name,
                customers.c.contact_name,
                customers.c.contact_email,
                customers.c.contact_phone,
            )
            .order_by(customers.c.name)
            .limit(limit)
            .offset(offset)
        )

        rows = conn.execute(stmt).mappings().all()

    contacts: List[ContactInfo] = []
    for row in rows:
        contacts.append(
            ContactInfo(
                contact_name=row["contact_name"],
                contact_email=row["contact_email"],
                contact_phone=row["contact_phone"],
                last_seen_invoice_date=row["last_seen_invoice_date"],
            )
        )

    # Use the name from the first row (they all share the same customer_name)
    customer_name = rows[0]["customer_name"] if rows else name

    return CustomerContactResponse(
        customer_name=customer_name,
        contacts=contacts,
        total=len(contacts),
    )


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int) -> CustomerOut:
    """
    Return a single customer by ID.
    """
    engine = get_engine()

    with engine.connect() as conn:
        stmt = (
            select(
                customers.c.id,
                customers.c.name,
                customers.c.contact_name,
                customers.c.contact_phone,
                customers.c.contact_email,
            )
            .where(customers.c.id == customer_id)
        )

        row = conn.execute(stmt).mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerOut(
        id=row["id"],
        name=row["name"],
        contact_name=row["contact_name"],
        contact_phone=row["contact_phone"],
        contact_email=row["contact_email"],
    )

