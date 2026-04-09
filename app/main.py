from fastapi import FastAPI
from app.api.routes import router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
import logging



logger = logging.getLogger(__name__)


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RTA Incident AI Engine",
    description="Classification, SOP Generation, and Review Queue for incident reports",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       
    allow_credentials=True,
    allow_methods=["*"],        
    allow_headers=["*"],
)


app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")                             
def serve_ui():
    return FileResponse("app/static/index.html")

app.mount("/static", StaticFiles(directory="app/static"), name="static")





@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified.")
    except Exception as e:
        logger.error(f"DB connection failed on startup: {e}")

