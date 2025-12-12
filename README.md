## 1. How to Run the Code

### 1.1. Install Dependencies

From the project directory:

```bash
cd /path/to/domeo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 1.2. Initialize the Database

This creates `db.sqlite` and builds the `customers` and `invoices` tables:

```bash
python -m scripts.init_db
```

---

### 1.3. Load the CSV Data

The assignment requires supporting two ingestion entrypoints, so both are implemented.

**Option A — Full ingestion pipeline:**

```bash
python -m scripts.ingest
```

This parses the CSV, validates the fields, and loads the results into SQLite.  
Invoices are upserted by `InvoiceNumber`, so the process is safe to run multiple times.

**Option B — Spec-required wrapper scripts:**

Parse only (no database writes):

```bash
python parse_data.py
```

Parse and load:

```bash
python load_data.py
```

Both wrapper scripts reuse the same parsing logic as the full pipeline.

---

### 1.4. Start the API Server

Run the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --reload
```

This launches the local API on port 8000.

Useful development URLs:

- **Swagger UI (interactive API tester):**  
  http://127.0.0.1:8000/docs

- **ReDoc (read-only API documentation):**  
  http://127.0.0.1:8000/redoc

- **Healthcheck:**  
  http://127.0.0.1:8000/health  
  Returns `{ "status": "ok" }` and is typically used by load balancers or orchestrators.


---

## 2. API Endpoints with Examples

The project exposes three GET endpoints. All endpoints return JSON and match the response formats defined in the assignment specification.

---

### 2.1. GET `/invoices/past-due`

**What it does:**  
Returns a paginated list of invoices that are past due. An invoice is past due when:  
- `outstanding = max(bill_total - applied, 0)` is greater than 0  
- and `due_date < as_of`

**Query parameters:**
- `as_of` (optional, ISO `YYYY-MM-DD`; default = today in America/New_York)  
- `limit` (default 50, max 200)  
- `offset` (default 0)  
- `sort` (`due_date.asc` or `due_date.desc`; default ascending)

**Example request:**

```
http://127.0.0.1:8000/invoices/past-due?as_of=2025-03-01&limit=5&offset=0&sort=due_date.asc
```

**Example response:**

```json
{
  "items": [
    {
      "invoice_number": "DF2014658",
      "customer_name": "LogicNest",
      "invoice_date": "2024-03-11",
      "due_date": "2024-04-10",
      "bill_total": "9400.00",
      "applied": "7138.90",
      "outstanding": "2261.10",
      "currency": "USD",
      "status": "Pending",
      "days_past_due": 325
    },
    {
      "invoice_number": "DF2014959",
      "customer_name": "LogicNest",
      "invoice_date": "2024-03-13",
      "due_date": "2024-04-12",
      "bill_total": "1200.00",
      "applied": "417.75",
      "outstanding": "782.25",
      "currency": "USD",
      "status": "Pending",
      "days_past_due": 323
    }
  ],
  "total": 28,
  "limit": 5,
  "offset": 0
}
```

---

### 2.2. GET `/invoices/summary/month`

**What it does:**  
Returns monthly invoice totals, including the total bill amount, invoice count, and currency.  
Supports optional filtering by customer name.

**Query parameters:**
- `month` (required, `YYYY-MM`)
- `customer_name` (optional, case-insensitive exact match)

**Example request (all customers):**
```
http://127.0.0.1:8000/invoices/summary/month?month=2024-11
```

**Example response:**

```json
{
  "month": "2024-11",
  "currency": "USD",
  "sum_bill_total": "318565.14",
  "count_invoices": 143
}
```

**Example request (filtered by customer):**
```
http://127.0.0.1:8000/invoices/summary/month?month=2024-11&customer_name=Lens%20%26%20Light
```

**Example response:**

```json
{
  "month": "2024-11",
  "currency": "USD",
  "sum_bill_total": "4550.00",
  "count_invoices": 2
}
```

---

### 2.3. GET `/customers/contact`

**What it does:**  
Returns contact information and the most recent invoice date for a given customer.  
If the customer does not exist, the endpoint returns 404.

**Query parameters:**
- `name` (required)  
- `limit` (default 10)  
- `offset` (default 0)

**Example request:**

```
http://127.0.0.1:8000/customers/contact?name=Lens%20%26%20Light
```

**Example response:**

```json
{
  "customer_name": "Lens & Light",
  "contacts": [
    {
      "contact_name": "Angela Scott",
      "contact_email": "angela@lensandlight.com",
      "contact_phone": "555-513-2964",
      "last_seen_invoice_date": "2025-01-27"
    }
  ],
  "total": 1
}
```


---

## 3. Database Design and Reasoning

### 3.1 Overview
The data is modeled using two tables:

- **`customers`** — one row per customer company  
- **`invoices`** — one row per invoice sent to a customer  

This matches the natural shape of the CSV, which contains many invoices per customer and repeated contact info.

---

### 3.2 `customers` Table

**Columns**
- `id` — integer primary key  
- `name` — unique customer name  
- `contact_name` — nullable contact person  
- `contact_phone` — nullable phone  
- `contact_email` — nullable email  

**Reasoning**
- Customer contact details should not be duplicated across thousands of invoice rows.  
- `name` is unique so that ingestion cannot create duplicates.  
- Contact fields are nullable because some rows have missing info; the ingestion logic fills them in when possible.

---

### 3.3 `invoices` Table

**Columns**
- `id` — integer primary key  
- `invoice_number` — unique natural key from CSV  
- `customer_id` — foreign key to `customers.id`  
- `invoice_date` — DATE  
- `due_date` — DATE  
- `customer_po_number` — text, optional  
- `bill_total` — `NUMERIC(18,2)`  
- `applied` — `NUMERIC(18,2)`  
- `status` — `"Closed"` or `"Pending"`  
- `currency` — `"USD"` (usually)  
- `customer_terms` — original terms string  
- `terms_days` — parsed number of days as integer  

**Reasoning**
- `invoice_number` is the natural identifier and supports idempotent ingestion.  
- Internal integer `id` is still used for relational consistency and efficient joins.  
- Money is `NUMERIC(18,2)` per assignment guidelines and to avoid floating-point drift.  
- Date fields are stored as ISO dates for correct filtering and sorting.  
- `terms_days` is stored because it simplifies computing `due_date` when the CSV omits it.

---

### 3.4 Relationships and Constraints

**Relationships**
- One customer → many invoices  
- Every invoice must belong to a customer  

**Constraints**
- `customers.name` is unique  
- `invoices.invoice_number` is unique  
- `invoices.customer_id` is a foreign key  
- `bill_total` and `applied` have CHECK constraints to enforce non-negative values  

**Reasoning**
These constraints ensure referential integrity and enable deterministic, safe ingestion runs.

---

### 3.5 Indexing and Query Performance

Indexes used:
- Unique index on `invoices.invoice_number`  
- Index on `invoices.customer_id`  
- Indexes on `invoice_date` and `due_date`  

**Reasoning**
- `/invoices/past-due` requires filtering by `due_date` and joining to `customers`.  
- `/invoices/summary/month` filters by month via `invoice_date`.  
- `/customers/contact` resolves a customer by `name` and then joins to invoices.  

The indexes ensure each required endpoint runs efficiently even with larger datasets.

---

### 3.6 Idempotent Ingestion Behavior

**Customers**
- Rebuilt on every ingestion run  
- The CSV fully defines customers, so this avoids drift and ensures determinism

**Invoices**
- Loaded via upsert:
  - Insert new invoice rows  
  - Update modified rows if `invoice_number` already exists  

This makes ingestion safe to run multiple times with the same or corrected CSV.



---

## 4. AWS Deployment Design (Services, Flow, Trade-offs)

### 4.1 Overview
In production, the goal is to run the FastAPI service reliably, securely, and with proper database support.  
A minimal and realistic AWS setup is:

**Client → Application Load Balancer → FastAPI container (ECS Fargate) → RDS PostgreSQL**

This replaces SQLite (great for local dev) with a production-grade managed database.

---

### 4.2 Services Used

#### **Compute: ECS with Fargate**
- Package this repo’s FastAPI app into a Docker image.
- Deploy it as an ECS service running on AWS Fargate.
- No servers/EC2 instances to maintain—AWS runs the containers.

#### **Database: Amazon RDS (PostgreSQL)**
- Same schema as the SQLite version, just migrated to Postgres.
- Supports concurrency, backups, and scaling.
- Exposed to the ECS tasks via a VPC subnet.

#### **Routing: Application Load Balancer (ALB)**
- Receives all HTTPS traffic.
- Terminates TLS and forwards requests to the ECS tasks.
- Uses `/health` for automatic health checks.

#### **Secrets & Configuration**
- Use **AWS Systems Manager Parameter Store** or **AWS Secrets Manager**  
  for:
  - `DATABASE_URL`
  - Any future API keys
- ECS injects these as environment variables into the container.

#### **Logging/Monitoring: CloudWatch**
- Collects logs from Uvicorn/FastAPI.
- Set alarms for:
  - High 5xx rates
  - Unhealthy task count
  - Latency spikes

---

### 4.3 Request Flow

1. Client sends HTTPS request to the **Application Load Balancer**.  
2. ALB forwards the request to an **ECS Fargate** task running the FastAPI app.  
3. FastAPI queries or updates invoice/customer data stored in **RDS PostgreSQL**.  
4. Response flows back through the ALB to the client.

This flow cleanly separates compute from storage and scales easily by increasing ECS task count.

---

### 4.4 Trade-offs & Rationale

- **Why not SQLite in prod?**  
  SQLite is ideal for local development but does not support safe concurrent writes or automatic backups.

- **Why ECS Fargate instead of EC2 or Kubernetes?**  
  - Fargate: fully managed, simplest to operate.  
  - EC2: more control, more maintenance.  
  - Kubernetes (EKS): powerful but unnecessary for a small API.

- **Why ALB instead of API Gateway?**  
  ALB is perfect for routing web traffic to a containerized API.  
  API Gateway is best when you need Lambda integration, request transformation, or heavy API management overhead.

- **Why Parameter Store/Secrets Manager?**  
  Keeps database credentials and configuration out of source control.  
  Container tasks receive secrets securely at runtime.

This setup is straightforward for a production environment, easy to maintain, and aligns with typical AWS patterns for container-based backend APIs.

<img width="5743" height="2405" alt="domeo_vertical_v_final_pretty" src="https://github.com/user-attachments/assets/958b2f38-14b2-4f62-8a1e-f81bbf99ad10" />

---
