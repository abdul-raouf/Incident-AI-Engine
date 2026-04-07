from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import urllib

# Build the pyodbc connection string explicitly, then pass to SQLAlchemy
# This avoids URL parsing issues with IP addresses and special chars in passwords
odbc_connect_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={settings.DB_HOST},{settings.DB_PORT};"
    f"DATABASE={settings.DB_NAME};"
    f"UID={settings.DB_USER};"
    f"PWD={settings.DB_PASSWORD};"
    f"TrustServerCertificate=yes;"
    f"&charset=utf8;" 
    f"&unicode_results=True;"  
)

# URL-encode the connection string for SQLAlchemy
connection_url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(odbc_connect_str)}"

engine = create_engine(connection_url, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()