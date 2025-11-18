-- schema_template.sql
-- Logical schema for Unicorn Inc AR data

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    contact_name TEXT,
    contact_phone TEXT,
    contact_email TEXT
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    invoice_number TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    customer_po_number TEXT,
    bill_total NUMERIC(18,2) NOT NULL,
    applied NUMERIC(18,2) NOT NULL,
    status TEXT,
    currency TEXT,
    customer_terms TEXT,
    terms_days INTEGER,
    CONSTRAINT fk_invoices_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id),
    CONSTRAINT ck_invoices_bill_total_nonneg
        CHECK (bill_total >= 0),
    CONSTRAINT ck_invoices_applied_nonneg
        CHECK (applied >= 0)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_invoices_customer_id
    ON invoices (customer_id);

CREATE INDEX IF NOT EXISTS idx_invoices_invoice_date
    ON invoices (invoice_date);

CREATE INDEX IF NOT EXISTS idx_invoices_due_date
    ON invoices (due_date);
