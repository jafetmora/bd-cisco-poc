from __future__ import annotations
from typing import Optional, List

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: int) -> Optional[Product]:
        return await self.session.get(Product, id_)

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        stmt = select(Product).where(Product.sku == sku)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def search(
        self, q: Optional[str] = None, *, limit: int = 10, offset: int = 0
    ) -> List[Product]:
        stmt = select(Product)
        if q:
            q = q.strip()
            if q:
                like = f"%{q}%"
                stmt = stmt.where(
                    or_(
                        Product.sku.ilike(like),
                        Product.name.ilike(like),
                        Product.description.ilike(like),
                        Product.category.ilike(like),
                    )
                )
        stmt = (
            stmt.order_by(Product.sku.asc(), Product.id.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
