from fastapi import FastAPI
from app.api.routes import router
from app.core.database import Base, engine
import logging

logger = logging.getLogger(__name__)


app = FastAPI(
    title="RTA Incident AI Engine",
    description="Classification, SOP Generation, and Review Queue for incident reports",
    version="1.0.0"
)

app.include_router(router)

@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified.")
    except Exception as e:
        logger.error(f"DB connection failed on startup: {e}")

@app.get("/health")
def health():
    return {"status": "ok"}