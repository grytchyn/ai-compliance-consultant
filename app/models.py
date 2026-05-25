<<<<<<< HEAD
from .database import Base, Submission, engine, SessionLocal

# Re-export for convenience
__all__ = ["Base", "Submission", "engine", "SessionLocal"]
=======
from sqlalchemy import Column, String, DateTime
from .database import Base
import datetime

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, index=True)
    company = Column(String, index=True)
    url = Column(String)
    description = Column(String)
    email = Column(String)
    status = Column(String, default="processing")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    report_path = Column(String, nullable=True)
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)
