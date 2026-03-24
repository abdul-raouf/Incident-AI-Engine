from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.schemas.pydantic_schemas import (
    AnalyzeRequest, AnalyzeResponse,
    ReviewQueueItem, ResolveReviewRequest, CategoryScore
)
from app.models.db_models import IncidentReport
from app.services.classifier import classify_text
from app.services.sop_engine import generate_sop
from app.services import review_queue as rq
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1", tags=["Incidents"])

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_incident(payload: AnalyzeRequest, db: Session = Depends(get_db)):

    # 1. Classify → full scored array
    classification = await classify_text(payload.text)

    # 2. Generate SOP using top category
    sop = await generate_sop(payload.text, classification)

    # 3. Flag if top confidence is below threshold or primary is Unknown
    is_flagged = (
        classification.primary_confidence < settings.CONFIDENCE_THRESHOLD or
        classification.primary_category.value == "Unknown"
    )

    # 4. Persist
    incident = IncidentReport(
        id                     = str(uuid.uuid4()),
        source                 = payload.source.value,
        report_type            = payload.report_type,
        raw_input              = payload.text,
        classification_scores  = [
            {"category": s.category.value, "confidence": s.confidence}
            for s in classification.scores
        ],
        primary_classification = classification.primary_category.value,
        primary_confidence     = classification.primary_confidence,
        reasoning              = classification.reasoning,
        sop_generated          = sop,
        is_flagged             = is_flagged,
        model_used             = settings.OLLAMA_MODEL,
        created_at             = datetime.now(timezone.utc)
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # 5. Queue for review if flagged
    if is_flagged:
        rq.flag_for_review(db, str(incident.id), classification)

    return AnalyzeResponse(
        id                     = str(incident.id),
        classifications        = classification.scores,
        primary_classification = incident.primary_classification,
        primary_confidence     = incident.primary_confidence,
        reasoning              = incident.reasoning,
        sop                    = incident.sop_generated,
        is_flagged             = incident.is_flagged,
        created_at             = incident.created_at
    )

@router.get("/review-queue", response_model=list[ReviewQueueItem])
def get_review_queue(db: Session = Depends(get_db)):
    items = rq.get_pending_reviews(db)
    return [
        ReviewQueueItem(
            id                     = str(item.id),
            incident_id            = str(item.incident_id),
            primary_classification = item.primary_classification,
            primary_confidence     = item.primary_confidence,
            all_scores             = [CategoryScore(**s) for s in item.all_scores],
            created_at             = item.created_at,
            resolved               = item.resolved
        )
        for item in items
    ]

@router.patch("/review-queue/{review_id}/resolve", response_model=ReviewQueueItem)
def resolve_review(
    review_id: str,
    payload:   ResolveReviewRequest,
    db:        Session = Depends(get_db)
):
    item = rq.resolve_review(db, review_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return ReviewQueueItem(
        id                     = str(item.id),
        incident_id            = str(item.incident_id),
        primary_classification = item.primary_classification,
        primary_confidence     = item.primary_confidence,
        all_scores             = [CategoryScore(**s) for s in item.all_scores],
        created_at             = item.created_at,
        resolved               = item.resolved
    )