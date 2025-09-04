from typing import Optional
from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from api.core.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(
        "type", String(100), nullable=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    partner_discount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
