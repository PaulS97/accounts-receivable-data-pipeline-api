# app/models/invoices.py

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class InvoiceOut(BaseModel):
    id: int
    invoice_number: str
    customer_id: int
    customer_name: str
    invoice_date: date
    due_date: date
    customer_po_number: Optional[str] = None
    bill_total: Decimal
    applied: Decimal
    status: Optional[str] = None
    currency: Optional[str] = None
    customer_terms: Optional[str] = None
    terms_days: Optional[int] = None

    class Config:
        from_attributes = True


class MonthlySummaryOut(BaseModel):
    month: str
    currency: str
    sum_bill_total: Decimal
    count_invoices: int



class PastDueInvoiceItem(BaseModel):
    invoice_number: str
    customer_name: str
    invoice_date: date
    due_date: date
    bill_total: Decimal
    applied: Decimal
    outstanding: Decimal
    currency: str
    status: str
    days_past_due: int


class PastDueResponse(BaseModel):
    items: List[PastDueInvoiceItem]
    total: int
    limit: int
    offset: int

