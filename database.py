from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from models import Base
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv(dotenv_path=".env")

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "safai_chat_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Build connection string
# Use psycopg driver explicitly (psycopg v3, not psycopg2)
if DB_PASSWORD:
    DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = f"postgresql+psycopg://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database by creating all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables created/verified successfully")
    except SQLAlchemyError as e:
        print(f"⚠ Error creating database tables: {e}")
        raise


def get_db() -> Session:
    """Dependency function for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

