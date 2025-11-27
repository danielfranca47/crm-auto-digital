from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db import get_db

router = APIRouter(prefix="", tags=["catalog"])


class ProductOut(BaseModel):
    code: str
    name: str
    description: Optional[str]

    class Config:
        orm_mode = True


class PlanOut(BaseModel):
    product_code: str
    code: str
    name: str
    billing_period: str

    class Config:
        orm_mode = True


@router.get("/products", response_model=List[ProductOut])
async def list_products(db: Session = Depends(get_db)):
    products = db.query(models.Product).filter(models.Product.is_active.is_(True)).all()
    return products


@router.get("/plans", response_model=List[PlanOut])
async def list_plans(
    product_code: Optional[str] = Query(None, description="Filter by product code"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Plan)
        .join(models.Product)
        .filter(models.Plan.is_active.is_(True), models.Product.is_active.is_(True))
    )

    if product_code:
        query = query.filter(models.Product.code == product_code)

    plans = query.all()
    return [
        PlanOut(
            product_code=plan.product.code,
            code=plan.code,
            name=plan.name,
            billing_period=plan.billing_period,
        )
        for plan in plans
    ]
