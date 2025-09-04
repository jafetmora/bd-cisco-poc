from typing import Optional
from pydantic import BaseModel


class ProductSchema(BaseModel):
    id: int
    name: Optional[str] = None
    sku: Optional[str] = None
    product_type: Optional[str] = None  # maps to DB column "type"
    category: Optional[str] = None
    price: float
    description: Optional[str] = None
    partner_discount: Optional[float] = None

    class Config:
        from_attributes = True
