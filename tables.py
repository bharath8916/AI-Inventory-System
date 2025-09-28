# api/tables.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base


# ---------------------- PRODUCT ----------------------
class Product(Base):
    __tablename__ = "product"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="ea")
    # Column name is 'metadata' in DB, but we avoid clashing with Base.metadata
    meta_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
        Index("ix_product_tenant", "tenant_id"),
    )

    # relationships (optional backrefs)
    stock_moves: Mapped[List["StockMovement"]] = relationship(back_populates="product")
    alerts: Mapped[List["Alert"]] = relationship(back_populates="product")
    sale_items: Mapped[List["SaleItem"]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product {self.sku} {self.name!r}>"


# ---------------------- LOCATION ----------------------
class Location(Base):
    __tablename__ = "location"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")

    __table_args__ = (Index("ix_location_tenant", "tenant_id"),)

    sales: Mapped[List["Sale"]] = relationship(back_populates="location")
    stock_moves: Mapped[List["StockMovement"]] = relationship(back_populates="location")
    alerts: Mapped[List["Alert"]] = relationship(back_populates="location")

    def __repr__(self) -> str:
        return f"<Location {self.name!r}>"


# ---------------------- SALE ----------------------
class Sale(Base):
    __tablename__ = "sale"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("location.id"), nullable=False
    )
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    meta_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    __table_args__ = (Index("ix_sale_tenant_created", "tenant_id", "created_at"),)

    location: Mapped["Location"] = relationship(back_populates="sales")
    items: Mapped[List["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )
    tenders: Mapped[List["SaleTender"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )
    cash_movements: Mapped[List["CashMovement"]] = relationship(back_populates="sale")

    def __repr__(self) -> str:
        return f"<Sale {self.id} total={self.total}>"


# ---------------------- SALE ITEM ----------------------
class SaleItem(Base):
    __tablename__ = "sale_item"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    sale_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    __table_args__ = (
        Index("ix_sale_item_sale", "sale_id"),
        Index("ix_sale_item_product", "product_id"),
    )

    sale: Mapped["Sale"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="sale_items")

    def __repr__(self) -> str:
        return f"<SaleItem sale={self.sale_id} product={self.product_id}>"


# ---------------------- SALE TENDER ----------------------
class SaleTender(Base):
    __tablename__ = "sale_tender"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    sale_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)   # 'cash','card',...
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="approved")
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "method in ('cash','card','check','money_order','store_credit','other')",
            name="ck_sale_tender_method",
        ),
        CheckConstraint(
            "status in ('pending','approved','returned')",
            name="ck_sale_tender_status",
        ),
        Index("ix_sale_tender_sale", "sale_id"),
    )

    sale: Mapped["Sale"] = relationship(back_populates="tenders")

    def __repr__(self) -> str:
        return f"<SaleTender sale={self.sale_id} {self.method} {self.amount}>"


# ---------------------- STOCK MOVEMENT ----------------------
class StockMovement(Base):
    __tablename__ = "stock_movement"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product.id"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("location.id"), nullable=False
    )
    delta_qty: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # 'sale','purchase','adjustment'
    ref_id: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "reason in ('sale','purchase','adjustment')",
            name="ck_stock_movement_reason",
        ),
        Index("ix_stock_movement_recent", "occurred_at"),
        Index("ix_stock_movement_tenant_occ", "tenant_id", "occurred_at"),
        Index("ix_stock_movement_tpl", "tenant_id", "product_id", "location_id"),
    )

    product: Mapped["Product"] = relationship(back_populates="stock_moves")
    location: Mapped["Location"] = relationship(back_populates="stock_moves")

    def __repr__(self) -> str:
        return f"<StockMovement product={self.product_id} qty={self.delta_qty}>"


# ---------------------- CASH MOVEMENT ----------------------
class CashMovement(Base):
    __tablename__ = "cash_movement"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("location.id"), nullable=False
    )
    sale_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)  # 'float_in','payout',...
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "type in ('float_in','payout','cashback','cash_sale','cash_refund','deposit')",
            name="ck_cash_movement_type",
        ),
        Index("ix_cash_movement_recent", "occurred_at"),
    )

    location: Mapped["Location"] = relationship()
    sale: Mapped[Optional["Sale"]] = relationship(back_populates="cash_movements")

    def __repr__(self) -> str:
        return f"<CashMovement {self.type} {self.amount}>"


# ---------------------- ALERT ----------------------
class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("product.id"))
    location_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("location.id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)  # 'low_stock','anomaly'
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("type in ('low_stock','anomaly')", name="ck_alert_type"),
    )

    product: Mapped[Optional["Product"]] = relationship(back_populates="alerts")
    location: Mapped[Optional["Location"]] = relationship(back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert {self.type} product={self.product_id} loc={self.location_id}>"
