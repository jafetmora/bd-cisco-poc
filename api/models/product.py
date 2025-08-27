from pydantic import BaseModel

class Product(BaseModel):
    family: str
    dimension: str
    sku: str
    description: str
    price: float
