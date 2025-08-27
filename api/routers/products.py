from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from api.models.product import Product

router = APIRouter()

# Dummy in-memory data for demonstration
PRODUCTS_DB = [
    Product(family="Switches", dimension="Meraki MS Hardware", sku="PWR-C5-125WAC-M", description="125W AC Config 5 Power Supply, w/Meraki", price=1567.47),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="PWR-C5-1KWAC-M", description="1KW AC Config 5 Power Supply, w/Meraki", price=906.16),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="STACK-T4-1M-M", description="1M Type 4 Stacking Cable, w/Meraki", price=2238.81),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="STACK-T4-3M-M", description="3M Type 4 Stacking Cable, w/Meraki", price=67.23),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="STACK-T4-50CM-M", description="50CM Type 4 Stacking Cable, w/Meraki", price=647.26),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="PWR-C5-600WAC-M", description="600W AC Config 5 Power Supply, w/Meraki", price=349.22),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="PWR-C1-1100WAC-P-M", description="C9000 1100W AC Platinum Power Supply, w/MERAKI", price=776.71),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="STACK-T1-1M-M", description="C9000 1M Type 1 Stacking Cable, w/MERAKI", price=596.08),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="PWR-C1-350WAC-P-M", description="C9000 350W AC Platinum Power Supply, w/MERAKI", price=1294.52),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="STACK-T1-3M-M", description="C9000 3M Type 1 Stacking Cable, w/MERAKI", price=6979.73),
    Product(family="Switches", dimension="Meraki MS Hardware", sku="4PT-KIT-T2-M", description="C9000 4 Point Type 1 rack mount kit, w/MERAKI", price=1718.55),
]


@router.get("/products", response_model=List[Product])
def search_products(
    q: Optional[str] = Query(None, description="Search string for SKU or description")
):
    """
    Search for products by SKU or description.
    """
    results = PRODUCTS_DB
    if q:
        q_lower = q.lower()
        results = [p for p in results if q_lower in p.sku.lower() or q_lower in p.description.lower()]
    if not results:
        raise HTTPException(status_code=404, detail="No products found")
    return results

