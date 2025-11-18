# app/__init__.py
"""
Package entrypoint for the FastAPI application.

This lets us run:
    uvicorn app:app --reload
"""

from .main import app

__all__ = ["app"]
