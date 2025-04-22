import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import (  # Standard import for SQLAlchemy 2.0+
    declarative_base, sessionmaker)

load_dotenv()  # Load values from .env

# Database configuration (Using SQLite for now; TODO: Move to PostgreSQL later)
# DATABASE_URL = "sqlite:///./database.db"
DATABASE_URL = os.getenv("DATABASE_URL")  # Pull from the .env file


# Create database engine (connection handler)
# Note: `check_same_thread=False` is required for SQLite when using multiple threads
engine = create_engine(DATABASE_URL)


# Session factory: This will be used to create new database sessions when needed
SessionLocal = sessionmaker(
    autocommit=False,  # Explicit commit required
    autoflush=False,  # This sometimes causes unexpected behavior if left True
    bind=engine,  # Bind session to our engine
)

# Base class for ORM models (All models should inherit from this)
Base = declarative_base()


# Dependency for getting a database session
# Note: FastAPI will use this function to provide a session in request handlers
def get_db():
    db = SessionLocal()  # Start a new session
    try:
        yield db  # Provide the session
    finally:
        db.close()  # Cleanup: Close the session after request is handled
