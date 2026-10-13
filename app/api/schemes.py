from fastapi import APIRouter, Body
from typing import Dict, Any
from app.services.scheme_service import SchemeService

router = APIRouter(prefix="/api", tags=["Government Schemes"])

@router.get("/schemes")
def list_schemes():
    """Returns verified agricultural schemes, benefits, documents, and application links."""
    return {"schemes": SchemeService.get_all_schemes()}

@router.post("/schemes/check")
def check_scheme_eligibility(payload: Dict[str, Any] = Body(...)):
    """
    Evaluates farmer eligibility for PM-KISAN, Namo Shetkari, PMFBY, and Subsidies.
    """
    land = float(payload.get("land_acres", 2.0))
    taxpayer = bool(payload.get("is_taxpayer", False))
    ekyc = bool(payload.get("ekyc_completed", True))
    saatbaara = bool(payload.get("has_saatbaara", True))

    return SchemeService.check_eligibility(
        land_acres=land,
        is_taxpayer=taxpayer,
        ekyc_completed=ekyc,
        has_saatbaara=saatbaara
    )
