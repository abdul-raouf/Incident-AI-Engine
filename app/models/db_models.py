from sqlalchemy import Column, String, Float, Text, DateTime, Boolean, Integer
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id              = Column(UNIQUEIDENTIFIER, primary_key=True, default=lambda: str(uuid.uuid4()))
    source          = Column(String(50),  nullable=False)   # video | call | text_report
    report_type     = Column(String(100), nullable=False)
    raw_input       = Column(Text,        nullable=False)
    classification_scores  = Column(JSON,        nullable=False)  
    primary_classification = Column(String(100), nullable=False)  
    primary_confidence     = Column(Float,       nullable=False)  
    reasoning       = Column(Text,        nullable=True)
    sop_generated   = Column(Text,        nullable=True)
    is_flagged      = Column(Boolean,     default=False)    # low confidence flag
    model_used      = Column(String(100), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id              = Column(UNIQUEIDENTIFIER, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id     = Column(UNIQUEIDENTIFIER, nullable=False)  # FK to incident_reports
    primary_classification = Column(String(100), nullable=False)
    primary_confidence     = Column(Float,       nullable=False)
    all_scores             = Column(JSON,        nullable=False)
    reviewer_notes  = Column(Text,        nullable=True)
    resolved        = Column(Boolean,     default=False)
    resolved_at     = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())