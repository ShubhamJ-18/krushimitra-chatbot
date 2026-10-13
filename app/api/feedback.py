from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.conversation import Feedback
from app.schemas.schemas import FeedbackRequest

router = APIRouter(prefix="/api", tags=["Feedback"])

@router.post("/feedback")
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    """Records farmer satisfaction rating and feedback."""
    entry = Feedback(
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment
    )
    db.add(entry)
    db.commit()
    return {"status": "success", "message": "Feedback received. Thank you for helping improve KrushiMitra AI."}
