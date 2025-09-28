'''from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME)

@app.get("/health")
def health():
    return {
        "app": settings.APP_NAME,
        "environment": settings.ENV,
        "status": "healthy",
        "db" : "configured" if settings.DATA_BASE_URL else "not configured"
    }'''
# api/app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from decimal import Decimal
from sqlalchemy import create_engine, text
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/invdb")
engine = create_engine(DB_URL, future=True, pool_pre_ping=True)

app = FastAPI(title="Inventory API")

TenderMethod = Literal["cash","card","check","money_order","store_credit","other"]

class SaleItemIn(BaseModel):
    product_id: str
    qty: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)

class TenderIn(BaseModel):
    method: TenderMethod
    amount: Decimal
    details: dict = Field(default_factory=dict)

class SaleIn(BaseModel):
    tenant_id: str
    location_id: str
    items: List[SaleItemIn] = Field(min_length=1)
    tenders: List[TenderIn] = Field(min_length=1)
    tax_rate: Decimal = Field(default=Decimal("0.10"), ge=0)
class ProductIn(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price: Decimal = Field(ge=0)
    metadata: dict = Field(default_factory=dict)
class LocationIn(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

class StockAjustmentIn(BaseModel):
    tenant_id: str
    product_id: str
    location_id: str
    delta_qty: Decimal
    reason: str
    ref_id: Optional[str] = None
class StockAdjustmentOut(BaseModel):
    id: str
    tenant_id: str
    product_id: str
    location_id: str
    delta_qty: Decimal
    reason: str
    ref_id: Optional[str] = None
    created_at: str
class InventoryItemOut(BaseModel):
    tenant_id: str
    product_id: str
    location_id: str
    on_hand: Decimal
@app.get("/")
def health():
    return {"ok": True}

@app.get("/v1/inventory")
def list_inventory(tenant_id: str, product_id: Optional[str] = None, location_id: Optional[str] = None):
    sql = """
      select tenant_id, product_id, location_id, on_hand
      from inventory_current
      where tenant_id = :t
        and (:p is null or product_id = :p)
        and (:l is null or location_id = :l)
      order by product_id, location_id
    """
    with engine.begin() as conn:
        rows = conn.execute(text(sql), {"t": tenant_id, "p": product_id, "l": location_id}).mappings().all()
    return {"data": rows}

@app.post("/v1/sales", status_code=201)
def create_sale(payload: SaleIn):
    subtotal = sum((Decimal(it.qty) * Decimal(it.unit_price) - Decimal(it.discount)) for it in payload.items)
    tax = (subtotal * payload.tax_rate).quantize(Decimal("0.01"))
    total = (subtotal + tax).quantize(Decimal("0.01"))

    paid = sum(Decimal(t.amount) for t in payload.tenders).quantize(Decimal("0.01"))
    if paid != total:
        raise HTTPException(400, detail=f"Tenders total {paid} != sale total {total}")

    with engine.begin() as conn:
        sale_id = conn.execute(text("""
            insert into sale (tenant_id, location_id, subtotal, tax, total, metadata)
            values (:t, :l, :sub, :tax, :tot, '{}'::jsonb)
            returning id
        """), {"t": payload.tenant_id, "l": payload.location_id,
               "sub": str(subtotal), "tax": str(tax), "tot": str(total)}).scalar_one()

        for it in payload.items:
            conn.execute(text("""
                insert into sale_item (tenant_id, sale_id, product_id, qty, unit_price, discount)
                values (:t, :sid, :pid, :q, :p, :d)
            """), {"t": payload.tenant_id, "sid": sale_id, "pid": it.product_id,
                   "q": str(it.qty), "p": str(it.unit_price), "d": str(it.discount)})

            conn.execute(text("""
                insert into stock_movement (tenant_id, product_id, location_id, delta_qty, reason, ref_id)
                values (:t, :pid, :l, :dq, 'sale', :sid)
            """), {"t": payload.tenant_id, "pid": it.product_id, "l": payload.location_id,
                   "dq": str(-it.qty), "sid": str(sale_id)})

        for t in payload.tenders:
            conn.execute(text("""
                insert into sale_tender (tenant_id, sale_id, method, amount, status, details)
                values (:t, :sid, :m, :a, 'approved', :det)
            """), {"t": payload.tenant_id, "sid": sale_id, "m": t.method,
                   "a": str(t.amount), "det": t.details})

            if t.method == "cash":
                cm_type = "cash_sale" if Decimal(t.amount) > 0 else "cashback"
                conn.execute(text("""
                    insert into cash_movement (tenant_id, location_id, sale_id, type, amount, note)
                    values (:t, :l, :sid, :ty, :a, :note)
                """), {"t": payload.tenant_id, "l": payload.location_id, "sid": sale_id,
                       "ty": cm_type, "a": str(t.amount), "note": "cash tender"})

        conn.execute(text("refresh materialized view inventory_current;"))

    return {"id": str(sale_id), "subtotal": str(subtotal), "tax": str(tax), "total": str(total)}
@app.post("/v1/products", status_code=201)
def create_product(payload: ProductIn):
    sql = """
        insert into product (id, name, description, price, metadata)
        values (:id, :name, :desc, :price, :meta::jsonb)
        on conflict (id) do update
          set name = excluded.name,
              description = excluded.description,
              price = excluded.price,
              metadata = excluded.metadata
        returning id
    """
    with engine.begin() as conn:
        prod_id = conn.execute(text(sql), {
            "id": payload.id,
            "name": payload.name,
            "desc": payload.description,
            "price": str(payload.price),
            "meta": payload.metadata
        }).scalar_one()
    return {"id": prod_id}      
@app.get("/v1/products/{product_id}")
def get_product(product_id: str):
    sql = "select id, name, description, price, metadata from product where id = :id"
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"id": product_id}).mappings().first()
    if not row:
        raise HTTPException(404, detail="Product not found")
    return row
@app.post("/v1/locations", status_code=201)
def create_location(payload: LocationIn):
    sql = """
        insert into location (id, name, address, metadata)
        values (:id, :name, :addr, :meta::jsonb)
        on conflict (id) do update
          set name = excluded.name,
              address = excluded.address,
              metadata = excluded.metadata
        returning id
    """
    with engine.begin() as conn:
        loc_id = conn.execute(text(sql), {
            "id": payload.id,
            "name": payload.name,
            "addr": payload.address,
            "meta": payload.metadata
        }).scalar_one()
    return {"id": loc_id}      
@app.get("/v1/locations/{location_id}")
def get_location(location_id: str):
    sql = "select id, name, address, metadata from location where id = :id"
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"id": location_id}).mappings().first()
    if not row:
        raise HTTPException(404, detail="Location not found")
    return row
@app.post("/v1/stock_adjustments", status_code=201)
def create_stock_adjustment(payload: StockAjustmentIn):
    sql = """
        insert into stock_movement (tenant_id, product_id, location_id, delta_qty, reason, ref_id)
        values (:t, :pid, :lid, :dq, :r, :rid)
        returning id
    """
    with engine.begin() as conn:
        adj_id = conn.execute(text(sql), {
            "t": payload.tenant_id,
            "pid": payload.product_id,
            "lid": payload.location_id,
            "dq": str(payload.delta_qty),
            "r": payload.reason,
            "rid": payload.ref_id
        }).scalar_one()
        conn.execute(text("refresh materialized view inventory_current;"))
    return {"id": adj_id}   
@app.get("/v1/stock_adjustments")
def list_stock_adjustments(tenant_id: str, product_id: Optional[str] = None, location_id: Optional[str] = None):
    sql = """
      select id, tenant_id, product_id, location_id, delta_qty, reason, ref_id, created_at
      from stock_movement
      where tenant_id = :t
        and (:p is null or product_id = :p)
        and (:l is null or location_id = :l)
      order by created_at desc
      limit 100
    """
    with engine.begin() as conn:
        rows = conn.execute(text(sql), {"t": tenant_id, "p": product_id, "l": location_id}).mappings().all()
    return {"data": rows}   
