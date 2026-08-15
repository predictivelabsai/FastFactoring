"""Entrypoint. All routing lives in app.py."""

from utils.config import settings
from app import app, serve  # noqa: F401

if __name__ == "__main__":
    serve(port=settings().port, reload=settings().app_env != "production")
