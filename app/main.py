from fastapi import FastAPI

from app.api.customers import router as customers_router
from app.api.invoices import router as invoices_router

app = FastAPI(
    title="Domeo Unicorn Inc AR API",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(customers_router)
app.include_router(invoices_router)
