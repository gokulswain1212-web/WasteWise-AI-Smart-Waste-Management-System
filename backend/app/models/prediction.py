from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func

from app.db.base import Base


class DiscountRecommendation(Base):
    __tablename__ = "discount_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(
        String(100),
        ForeignKey("inventory_batches.batch_id"),
        nullable=True,
    )
    product_id = Column(
        String(100), ForeignKey("products.product_id"), nullable=False
    )
    days_to_expiry = Column(Integer, nullable=True)
    quantity_remaining = Column(Integer, nullable=True)
    discount_pct = Column(Numeric(7, 3), nullable=True)
    predicted_gross_margin = Column(Numeric(14, 2), nullable=True)
    estimated_units_sold_simulated = Column(Integer, nullable=True)
    estimated_revenue_simulated = Column(Numeric(14, 2), nullable=True)
    estimated_gross_margin_simulated = Column(Numeric(14, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
