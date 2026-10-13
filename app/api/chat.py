import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.schemas import ChatRequest, ChatResponse, ConversationSummary
from app.services.ai_service import AIService

router = APIRouter(prefix="/api", tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Main conversational AI endpoint.
    Maintains conversation context across turns, retrieves RAG documents,
    and returns evidence-backed agricultural guidance.
    """
    # Find or create conversation
    conv_id = payload.conversation_id
    conversation = None
    if conv_id:
        conversation = db.query(Conversation).filter(Conversation.id == conv_id).first()

    if not conversation:
        conv_id = str(uuid.uuid4())
        # Generate title from first query
        first_title = payload.message[:35] + ("..." if len(payload.message) > 35 else "")
        conversation = Conversation(
            id=conv_id,
            title=first_title,
            language=payload.language or "English"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Retrieve 10 most recent messages for conversation memory in chronological order
    recent_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    history_dicts = [{"role": m.role, "content": m.content} for m in reversed(recent_messages)]

    # Save user message
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=payload.message
    )
    db.add(user_msg)
    db.commit()

    # Generate response
    reply_text, intent, citations, follow_ups = await AIService.generate_response(
        query=payload.message,
        conversation_history=history_dicts,
        language=payload.language or conversation.language,
        district=payload.district or "Maharashtra"
    )

    # Save assistant message
    serialized_citations = json.dumps([c.model_dump() for c in citations]) if citations else None
    bot_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=reply_text,
        sources=serialized_citations,
        intent=intent
    )
    db.add(bot_msg)
    db.commit()

    return ChatResponse(
        conversation_id=conv_id,
        message=reply_text,
        intent=intent,
        sources=citations,
        follow_up_questions=follow_ups,
        language=payload.language or conversation.language
    )

@router.get("/conversations", response_model=List[ConversationSummary])
def get_conversations(db: Session = Depends(get_db)):
    """Returns recent conversations ordered by most recently updated."""
    conversations = (
        db.query(Conversation)
        .order_by(Conversation.updated_at.desc())
        .limit(30)
        .all()
    )
    results = []
    for c in conversations:
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        results.append(ConversationSummary(
            id=c.id,
            title=c.title,
            language=c.language,
            updated_at=c.updated_at,
            message_count=msg_count
        ))
    return results

@router.get("/conversations/{conversation_id}")
def get_conversation_detail(conversation_id: str, db: Session = Depends(get_db)):
    """Retrieves all messages for a specific conversation session."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return {
        "id": conv.id,
        "title": conv.title,
        "language": conv.language,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources) if m.sources else [],
                "created_at": m.created_at
            }
            for m in messages
        ]
    }

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Deletes a conversation and its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation deleted successfully"}
