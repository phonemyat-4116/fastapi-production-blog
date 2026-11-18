from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./blog.db"

# engine = creat_engine(
#     SQLALCHEMY_DATABASE_URL, 
#     connect_args={"check_same_thread": False} # Allows SQLite connections to be used across different threads
# )

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} # Allows SQLite connections to be used across different threads
)


# using async
AsyncSession = async_sessionmaker( # to create database sessions
    # autocommit = False, # these three are for sync
    # autoflush = False,
    # bind = engine

    engine,
    class_= AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase): # This is the parent class for your ORM models.
    pass

async def get_db():
    # with SessionLocal() as db: # This function is a dependency that provides a database session to your route handlers. It ensures that the session is properly closed after use.
    #     yield db
    async with AsyncSession() as session:
        yield session


