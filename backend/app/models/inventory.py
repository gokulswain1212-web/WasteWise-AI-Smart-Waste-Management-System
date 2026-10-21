from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer, Numeric, String
)

from app.db.base import Base


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    batch_id = Column(String(100), primary_key=True)
    product_id = Column(
        String(100), ForeignKey("products.product_id"), nullable=False
    )
    category = Column(String(100), nullable=True)
    received_at = Column(DateTime, nullable=True)
    snapshot_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    initial_quantity = Column(Integer, nullable=True)
    quantity_remaining = Column(Integer, nullable=True)
    days_to_expiry = Column(Integer, nullable=True)
    avg_daily_sales_7d = Column(Numeric(14, 4), nullable=True)
    expected_demand_before_expiry = Column(Numeric(14, 4), nullable=True)
    unit_price = Column(Numeric(12, 2), nullable=True)
    unit_cost = Column(Numeric(12, 2), nullable=True)
    discount_pct = Column(Numeric(7, 3), nullable=True)
    expiry_risk_label = Column(String(50), nullable=True)
    waste_units_actual_simulated = Column(Integer, nullable=True)


class PerishableInventory(Base):
    __tablename__ = "perishable_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        String(100), ForeignKey("products.product_id"), nullable=False
    )
    date = Column(Date, nullable=False)
    category = Column(String(100), nullable=True)
    opening_stock = Column(Integer, nullable=True)
    units_received = Column(Integer, nullable=True)
    units_sold = Column(Integer, nullable=True)
    unit_price = Column(Numeric(12, 2), nullable=True)
    discount_pct = Column(Numeric(7, 3), nullable=True)
    days_to_expiry = Column(Integer, nullable=True)
    temperature_c = Column(Numeric(6, 2), nullable=True)
    stockout_flag = Column(Integer, nullable=True)
    waste_units = Column(Integer, nullable=True)
