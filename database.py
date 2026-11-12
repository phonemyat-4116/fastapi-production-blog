from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./blog.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} # Allows SQLite connections to be used across different threads
)

SessionLocal = sessionmaker( # to create database sessions
    autocommit = False,
    autoflush = False,
    bind = engine
)

class Base(DeclarativeBase): # This is the parent class for your ORM models.
    pass

def get_db():
    with SessionLocal() as db: # This function is a dependency that provides a database session to your route handlers. It ensures that the session is properly closed after use.
        yield db

