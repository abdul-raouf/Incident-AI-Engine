from sqlalchemy.orm import Session
from app.models.db_models import ReviewQueue
from app.schemas.pydantic_schemas import ResolveReviewRequest, ClassificationOutput
from datetime import datetime, timezone
import uuid

def flag_for_review(
    db:             Session,
    incident_id:    str,
    classification: ClassificationOutput
) -> ReviewQueue:
    item = ReviewQueue(
        id                     = str(uuid.uuid4()),
        incident_id            = incident_id,
        primary_classification = classification.primary_category.value,
        primary_confidence     = classification.primary_confidence,
        all_scores             = [
            {"category": s.category.value, "confidence": s.confidence}
            for s in classification.scores
        ],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def get_pending_reviews(db: Session) -> list[ReviewQueue]:
    return db.query(ReviewQueue).filter(ReviewQueue.resolved == False).all()

def resolve_review(
    db:        Session,
    review_id: str,
    payload:   ResolveReviewRequest
) -> ReviewQueue | None:
    item = db.query(ReviewQueue).filter(ReviewQueue.id == review_id).first()
    if not item:
        return None
    item.primary_classification = payload.correct_classification.value
    item.reviewer_notes         = payload.reviewer_notes
    item.resolved               = True
    item.resolved_at            = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item