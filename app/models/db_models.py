from sqlalchemy import Column, Float, Text, DateTime, Boolean, Unicode, UnicodeText
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id              = Column(UNIQUEIDENTIFIER, primary_key=True, default=lambda: str(uuid.uuid4()))
    source          = Column(NVARCHAR(50),  nullable=False)   # video | call | text_report
    report_type     = Column(NVARCHAR(100), nullable=False)
    raw_input       = Column(UnicodeText,        nullable=False)
    classification_scores  = Column(JSON,        nullable=False)  
    primary_classification = Column(NVARCHAR(100), nullable=False)  
    primary_confidence     = Column(Float,       nullable=False)  
    reasoning       = Column(UnicodeText,        nullable=True)
    sop_generated   = Column(UnicodeText,        nullable=True)
    is_flagged      = Column(Boolean,     default=False)    # low confidence flag
    model_used      = Column(NVARCHAR(100), nullable=True)
    detected_language = Column(NVARCHAR(10), nullable=False, default="en")
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id              = Column(UNIQUEIDENTIFIER, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id     = Column(UNIQUEIDENTIFIER, nullable=False)  # FK to incident_reports
    primary_classification = Column(NVARCHAR(100), nullable=False)
    primary_confidence     = Column(Float,       nullable=False)
    all_scores             = Column(JSON,        nullable=False)
    reviewer_notes  = Column(UnicodeText,        nullable=True)
    resolved        = Column(Boolean,     default=False)
    resolved_at     = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())