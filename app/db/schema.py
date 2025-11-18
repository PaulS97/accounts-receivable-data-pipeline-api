# app/db/schema.py

from sqlalchemy import (
    MetaData, Table, Column, Integer, String,
    Numeric, Date, ForeignKey, CheckConstraint, Text
)

metadata = MetaData()

customers = Table(
    "customers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False, unique=True),
    Column("contact_name", String, nullable=True),
    Column("contact_phone", String, nullable=True),
    Column("contact_email", String, nullable=True),
)

invoices = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("invoice_number", Text, unique=True, nullable=False),
    Column("customer_id", Integer, ForeignKey("customers.id"), nullable=False),
    Column("invoice_date", Date, nullable=False),
    Column("due_date", Date, nullable=False),
    Column("customer_po_number", Text),
    Column("bill_total", Numeric(18, 2), nullable=False),
    Column("applied", Numeric(18, 2), nullable=False),
    Column("status", Text),
    Column("currency", Text),
    Column("customer_terms", Text),
    Column("terms_days", Integer),
    CheckConstraint("bill_total >= 0", name="ck_invoices_bill_total_nonneg"),
    CheckConstraint("applied >= 0", name="ck_invoices_applied_nonneg"),
)
