from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./sort_bot_leaderboard.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False, 
        "timeout": 30,  # Wait up to 30s for a 3locked DB before erroring
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()