"""
SQLAlchemy declarative base for WasteWise AI database models.

This module provides the `Base` class that all SQLAlchemy models inherit from.
Currently no model classes are defined here — the model files under
`backend/app/models/` are empty placeholders. When models are added later,
they should inherit from this Base.

Usage:
    from app.db.base import Base

    class Product(Base):
        __tablename__ = "products"
        ...
"""

from __future__ import annotations

from sqlalchemy.orm import declarative_base

Base = declarative_base()
