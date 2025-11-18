# app/models/customers.py

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class CustomerOut(BaseModel):
    id: int
    name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None

    class Config:
        from_attributes = True


class ContactInfo(BaseModel):
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    last_seen_invoice_date: Optional[date] = None


class CustomerContactResponse(BaseModel):
    customer_name: str
    contacts: List[ContactInfo]
    total: int
