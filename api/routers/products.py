from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from api.core.db import get_db
from api.schemas.product import ProductSchema
from api.repositories.product import ProductRepository

router = APIRouter()


@router.get("/products", response_model=List[ProductSchema])
async def search_products(
    q: Optional[str] = Query(
        None, description="Search string for SKU, name, category or description"
    ),
    session: AsyncSession = Depends(get_db),
):
    """
    Search for products by SKU, name, category or description.
    """
    repo = ProductRepository(session)
    results = await repo.search(q)
    if not results:
        raise HTTPException(status_code=404, detail="No products found")
    return results
