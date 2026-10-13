from fastapi import APIRouter, Query
from typing import Optional
from app.schemas.schemas import WeatherResponse
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/api", tags=["Weather"])

@router.get("/weather", response_model=WeatherResponse)
async def get_weather(district: Optional[str] = Query("Pune", description="District name in India")):
    """
    Returns real-time weather and agricultural advisory (spraying safety, irrigation necessity, heat risk)
    for the specified district.
    """
    return await WeatherService.get_district_weather(district)
