from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class MessageSchema(BaseModel):
    role: str
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Farmer's query")
    conversation_id: Optional[str] = None
    language: Optional[str] = "English"
    district: Optional[str] = "Maharashtra"
    crop: Optional[str] = None
    stage: Optional[str] = None
    symptoms: Optional[str] = None

class SourceCitation(BaseModel):
    title: str
    source_name: str
    source_url: Optional[str] = None
    publication_date: Optional[str] = None
    relevance_summary: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    intent: str
    sources: List[SourceCitation] = []
    follow_up_questions: List[str] = []
    language: str

class CropAnalysisRequest(BaseModel):
    image_base64: Optional[str] = None
    crop_name: Optional[str] = None
    language: Optional[str] = "English"
    additional_notes: Optional[str] = None

class CropAnalysisResponse(BaseModel):
    observed_symptoms: str
    possible_diagnosis: str
    severity: str
    confidence: str
    organic_treatment: List[str]
    chemical_treatment: List[str]
    prevention_measures: List[str]
    expert_escalation_needed: bool
    sources: List[SourceCitation] = []
    language: str

class SimpleCropDoctorRequest(BaseModel):
    query: Optional[str] = None
    crop: Optional[str] = None
    problem_type: Optional[str] = None  # yellow_leaves, pests, wilting, leaf_spots, rotten_fruit, other
    plant_part: Optional[str] = None    # lower_leaves, new_leaves, entire_plant, not_sure
    spread: Optional[str] = None        # few_plants, many_plants, whole_field, not_sure
    timeline: Optional[str] = None      # today, few_days, week_plus, not_sure
    image_base64: Optional[str] = None
    images_base64: Optional[List[str]] = None
    language: Optional[str] = "English"
    district: Optional[str] = "Maharashtra"

class SimpleCropDoctorResponse(BaseModel):
    crop: str
    symptoms_noticed: str
    possible_reasons: str
    immediate_actions: List[str]
    what_to_avoid: str
    expert_helpline: str
    audio_narration: str
    follow_up_question: Optional[Dict[str, Any]] = None
    sources: List[SourceCitation] = []
    language: str

class WeatherResponse(BaseModel):
    district: str
    temperature_c: float
    humidity_pct: int
    rainfall_mm: float
    wind_speed_kmh: float
    condition: str
    forecast_period: str
    source: str
    last_updated: str
    spraying_advisory: str
    irrigation_advisory: str
    agromet_alerts: List[str]

class MandiPriceItem(BaseModel):
    commodity: str
    variety: Optional[str] = None
    market: str
    district: str
    state: str
    unit: str
    min_price: float
    max_price: float
    modal_price: float
    arrival_quantity: Optional[str] = None
    trend: str
    report_date: str

class MandiPricesResponse(BaseModel):
    source: str
    source_url: str
    disclaimer: str
    last_updated: str
    commodities: List[MandiPriceItem]

class FeedbackRequest(BaseModel):
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class FarmerProfileSchema(BaseModel):
    name: str = "Farmer"
    district: str = "Pune"
    state: str = "Maharashtra"
    farm_size_acres: str = "3-5"
    primary_crops: str = "Soybean, Cotton, Onion"
    irrigation_type: str = "Drip / Well"
    preferred_language: str = "Marathi"

class ConversationSummary(BaseModel):
    id: str
    title: str
    language: str
    updated_at: datetime
    message_count: int
