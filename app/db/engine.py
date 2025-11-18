# app/db/engine.py

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DB_URL = "sqlite:///db.sqlite"  # file in project root

def get_engine() -> Engine:
    # echo=True if you want to see SQL printed in the terminal
    return create_engine(DB_URL, future=True)
