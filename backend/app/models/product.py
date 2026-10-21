from sqlalchemy import Column, Integer, Numeric, String

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(100), primary_key=True)
    product_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    shelf_life_days = Column(Integer, nullable=True)
    selling_price = Column(Numeric(12, 2), nullable=True)
    unit_cost = Column(Numeric(12, 2), nullable=True)
