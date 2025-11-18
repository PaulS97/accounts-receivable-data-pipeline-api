# app.py
"""
Thin entrypoint for the API, as requested in the assessment spec.

Usage example:
    uvicorn app:app --reload
"""

from app.main import app  # re-export FastAPI instance
