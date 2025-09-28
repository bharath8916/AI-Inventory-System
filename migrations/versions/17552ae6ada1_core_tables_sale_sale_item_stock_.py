
"""
core tables: sale, sale_item, stock_movement, inventory_current, tenders, alerts

Revision ID: 17552ae6ada1
Revises: ef0ef1f5fe51
Create Date: 2025-09-26 14:27:21.868091
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = "17552ae6ada1"
down_revision: Union[str, Sequence[str], None] = "ef0ef1f5fe51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # UUIDs
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ---------- Base tables (needed for FKs) ----------
    op.create_table(
        "product",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=False, server_default="ea"),
        sa.Column("metadata", pg.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
    )

    op.create_table(
        "location",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
    )

    # ---------- sale ----------
    op.create_table(
        "sale",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("location_id", pg.UUID(as_uuid=True), sa.ForeignKey("location.id"), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", pg.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_sale_tenant_created", "sale", ["tenant_id", "created_at"])

    # ---------- sale_item ----------
    op.create_table(
        "sale_item",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sale_id", pg.UUID(as_uuid=True), sa.ForeignKey("sale.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )

    # ---------- sale_tender (NOT 'sales_tender') ----------
    op.create_table(
        "sale_tender",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sale_id", pg.UUID(as_uuid=True), sa.ForeignKey("sale.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),  # 'cash','card','check','money_order','store_credit','other'
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),  # cashback => negative cash amount
        sa.Column("status", sa.Text(), nullable=False, server_default="approved"),  # 'pending','approved','returned'
        sa.Column("details", pg.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_sale_tender_method",
        "sale_tender",
        "method in ('cash','card','check','money_order','store_credit','other')",
    )
    op.create_check_constraint(
        "ck_sale_tender_status",
        "sale_tender",
        "status in ('pending','approved','returned')",
    )

    # ---------- stock_movement ----------
    op.create_table(
        "stock_movement",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("location_id", pg.UUID(as_uuid=True), sa.ForeignKey("location.id"), nullable=False),
        sa.Column("delta_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),  # 'sale','purchase','adjustment'
        sa.Column("ref_id", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_stock_movement_reason",
        "stock_movement",
        "reason in ('sale','purchase','adjustment')",
    )
    op.create_index("ix_stock_movement_recent", "stock_movement", ["occurred_at"])
    op.create_index("ix_stock_movement_tenant_occ", "stock_movement", ["tenant_id", "occurred_at"])

    # ---------- cash_movement ----------
    op.create_table(
        "cash_movement",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("location_id", pg.UUID(as_uuid=True), sa.ForeignKey("location.id"), nullable=False),
        sa.Column("sale_id", pg.UUID(as_uuid=True), sa.ForeignKey("sale.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),  # 'float_in','payout','cashback','cash_sale','cash_refund','deposit'
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_cash_movement_type",
        "cash_movement",
        "type in ('float_in','payout','cashback','cash_sale','cash_refund','deposit')",
    )
    op.create_index("ix_cash_movement_recent", "cash_movement", ["occurred_at"])

    # ---------- alert ----------
    op.create_table(
        "alert",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("product.id"), nullable=True),
        sa.Column("location_id", pg.UUID(as_uuid=True), sa.ForeignKey("location.id"), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),  # 'low_stock','anomaly'
        sa.Column("payload", pg.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_alert_type",
        "alert",
        "type in ('low_stock','anomaly')",
    )

    # ---------- inventory_current (MATERIALIZED VIEW) ----------
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS inventory_current AS
        SELECT tenant_id, product_id, location_id, SUM(delta_qty)::numeric(14,3) AS on_hand
        FROM stock_movement
        GROUP BY tenant_id, product_id, location_id;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inventory_current_tpl ON inventory_current (tenant_id, product_id, location_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_inventory_current_tpl;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS inventory_current;")
    op.drop_constraint("ck_alert_type", "alert", type_="check")
    op.drop_table("alert")
    op.drop_index("ix_cash_movement_recent", table_name="cash_movement")
    op.drop_constraint("ck_cash_movement_type", "cash_movement", type_="check")
    op.drop_table("cash_movement")
    op.drop_index("ix_stock_movement_tenant_occ", table_name="stock_movement")
    op.drop_index("ix_stock_movement_recent", table_name="stock_movement")
    op.drop_constraint("ck_stock_movement_reason", "stock_movement", type_="check")
    op.drop_table("stock_movement")
    op.drop_table("sale_tender")
    op.drop_table("sale_item")
    op.drop_index("ix_sale_tenant_created", table_name="sale")
    op.drop_table("sale")
    op.drop_table("location")
    op.drop_table("product")

