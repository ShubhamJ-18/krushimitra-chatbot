from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.conversation import FarmerProfile
from app.schemas.schemas import FarmerProfileSchema

router = APIRouter(prefix="/api", tags=["Profile"])

@router.get("/profile", response_model=FarmerProfileSchema)
def get_farmer_profile(db: Session = Depends(get_db)):
    """Retrieves farmer's optional farm profile."""
    profile = db.query(FarmerProfile).first()
    if not profile:
        profile = FarmerProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return FarmerProfileSchema(
        name=profile.name,
        district=profile.district,
        state=profile.state,
        farm_size_acres=profile.farm_size_acres,
        primary_crops=profile.primary_crops,
        irrigation_type=profile.irrigation_type,
        preferred_language=profile.preferred_language
    )

@router.put("/profile", response_model=FarmerProfileSchema)
def update_farmer_profile(payload: FarmerProfileSchema, db: Session = Depends(get_db)):
    """Updates farmer's profile with their explicit consent."""
    profile = db.query(FarmerProfile).first()
    if not profile:
        profile = FarmerProfile()
        db.add(profile)

    profile.name = payload.name
    profile.district = payload.district
    profile.state = payload.state
    profile.farm_size_acres = payload.farm_size_acres
    profile.primary_crops = payload.primary_crops
    profile.irrigation_type = payload.irrigation_type
    profile.preferred_language = payload.preferred_language

    db.commit()
    db.refresh(profile)
    return payload
