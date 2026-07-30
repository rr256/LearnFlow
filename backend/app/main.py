"""Uvicorn entry point.

Run locally from the ``backend`` directory with:

    python -m uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.composition.app_factory import create_app

app: FastAPI = create_app()
