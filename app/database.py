<<<<<<< HEAD
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
=======
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

<<<<<<< HEAD
Base = declarative_base()

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, index=True)
    url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    email = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, processing, done, error
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    report_path = Column(String, nullable=True)
=======
Base = declarative_base()
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)
