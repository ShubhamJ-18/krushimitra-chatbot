from fastapi import APIRouter, Query
from typing import Optional
from app.schemas.schemas import MandiPricesResponse
from app.services.mandi_service import MandiService

router = APIRouter(prefix="/api", tags=["Market Prices"])

@router.get("/market-prices", response_model=MandiPricesResponse)
def get_market_prices(
    commodity: Optional[str] = Query(None, description="Commodity name e.g. Onion, Soybean, Cotton"),
    district: Optional[str] = Query(None, description="District or APMC market name")
):
    """
    Returns verified APMC mandi wholesale rates.
    """
    return MandiService.get_prices(commodity_filter=commodity, district_filter=district)
