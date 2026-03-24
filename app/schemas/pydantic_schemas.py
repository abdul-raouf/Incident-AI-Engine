from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from datetime import datetime
from enum import Enum
from uuid import UUID

# ── Enums ────────────────────────────────────────────────────────────────────

class IncidentCategory(str, Enum):
    FIGHT                = "Fight"
    FIRE                 = "Fire"
    ACCIDENT             = "Accident"
    SUSPICIOUS_BEHAVIOUR = "Suspicious Behaviour"
    UNKNOWN              = "Unknown"

class SourceType(str, Enum):
    VIDEO       = "video"
    CALL        = "call"
    TEXT_REPORT = "text_report"

class CategoryScore(BaseModel):
    """One category with its confidence percentage."""
    category:   IncidentCategory = Field(..., description="The incident category")
    confidence: float            = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0–1.0")


# ── LLM Internal Schema ───────────────────────────────────────────────────────

# class ClassificationOutput(BaseModel):
#     category:   IncidentCategory = Field(..., description="The incident category")
#     confidence: float            = Field(..., ge=0.0, le=1.0)
#     reasoning:  str              = Field(..., description="Brief reasoning")


class ClassificationOutput(BaseModel):
    """
    All categories scored. Scores do not need to sum to 1.0 —
    each is an independent relevance score.
    Primary classification is the highest-scoring category.
    """
    scores:    List[CategoryScore] = Field(..., description="All categories with confidence scores")
    reasoning: str                 = Field(..., description="Brief reasoning for top classification")

    @property
    def primary(self) -> CategoryScore:
        """Returns the highest confidence category."""
        return max(self.scores, key=lambda x: x.confidence)

    @property
    def primary_confidence(self) -> float:
        return self.primary.confidence

    @property
    def primary_category(self) -> IncidentCategory:
        return self.primary.category

# ── API Request / Response ────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text:        str        = Field(..., description="The transcription or report text to analyze")
    source:      SourceType = Field(..., description="Source type of the input")
    report_type: str        = Field(..., description="Descriptive report type e.g. 'Station CCTV Report'")

class AnalyzeResponse(BaseModel):
    id:                     str
    classifications:        List[CategoryScore]   # ← full scored array
    primary_classification: str                   # ← top category name
    primary_confidence:     float
    reasoning:              str
    sop:                    str
    is_flagged:             bool
    created_at:             datetime

class ReviewQueueItem(BaseModel):
    id:                     str
    incident_id:            str
    primary_classification: str
    primary_confidence:     float
    all_scores:             List[CategoryScore]
    created_at:             datetime
    resolved:               bool

class ResolveReviewRequest(BaseModel):
    correct_classification: IncidentCategory
    reviewer_notes:         Optional[str] = None