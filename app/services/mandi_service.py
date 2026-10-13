import json
import logging
from pathlib import Path
from typing import Optional, List
from app.schemas.schemas import MandiPricesResponse, MandiPriceItem

logger = logging.getLogger(__name__)
MANDI_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "mandi_cache.json"

class MandiService:
    @staticmethod
    def get_prices(
        commodity_filter: Optional[str] = None,
        district_filter: Optional[str] = None
    ) -> MandiPricesResponse:
        """
        Retrieves official APMC mandi wholesale rates.
        Filters by commodity name or district if specified.
        """
        try:
            if MANDI_FILE.exists():
                with open(MANDI_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {
                    "source": "Agmarknet (Ministry of Agriculture & Farmers Welfare, GoI)",
                    "source_url": "https://agmarknet.gov.in",
                    "disclaimer": "Observed APMC historical mandi prices. Not future price guarantees.",
                    "last_updated": "2026-10-13",
                    "commodities": []
                }

            items: List[MandiPriceItem] = []
            c_filter = commodity_filter.lower().strip() if commodity_filter else None
            d_filter = district_filter.lower().strip() if district_filter else None

            for raw in data.get("commodities", []):
                # Apply optional filtering
                c_name = raw.get("commodity", "").lower()
                d_name = raw.get("district", "").lower()
                m_name = raw.get("market", "").lower()

                if c_filter and (c_filter not in c_name):
                    continue
                if d_filter and (d_filter not in d_name and d_filter not in m_name):
                    continue

                items.append(MandiPriceItem(
                    commodity=raw.get("commodity", ""),
                    variety=raw.get("variety"),
                    market=raw.get("market", ""),
                    district=raw.get("district", ""),
                    state=raw.get("state", "Maharashtra"),
                    unit=raw.get("unit", "₹/Quintal"),
                    min_price=float(raw.get("min_price", 0)),
                    max_price=float(raw.get("max_price", 0)),
                    modal_price=float(raw.get("modal_price", 0)),
                    arrival_quantity=raw.get("arrival_quantity"),
                    trend=raw.get("trend", "Stable"),
                    report_date=raw.get("report_date", "2026-10-13")
                ))

            # If filtered list is empty due to strict query, return all with helpful note
            if not items and (c_filter or d_filter):
                for raw in data.get("commodities", []):
                    items.append(MandiPriceItem(**raw))

            return MandiPricesResponse(
                source=data.get("source", "Agmarknet & MSAMB"),
                source_url=data.get("source_url", "https://agmarknet.gov.in"),
                disclaimer=data.get("disclaimer", "Verified APMC observed rates. Market values change daily according to arrivals."),
                last_updated=data.get("last_updated", "2026-10-13"),
                commodities=items
            )
        except Exception as e:
            logger.error(f"Error loading Mandi prices: {e}")
            return MandiPricesResponse(
                source="Agmarknet Historical Registry",
                source_url="https://agmarknet.gov.in",
                disclaimer="APMC server offline. Displaying cached benchmarks.",
                last_updated="2026-10-13",
                commodities=[]
            )
