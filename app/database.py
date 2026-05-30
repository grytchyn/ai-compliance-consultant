from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os
import json

# Use DATABASE_URL from environment for Render, fallback to local SQLite
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)  # uuid
    google_sub = Column(String, unique=True, index=True, nullable=False)  # Google's unique user ID
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "created_at": str(self.created_at) if self.created_at else None,
            "last_login": str(self.last_login) if self.last_login else None,
        }


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)  # FK to users.id
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    report_path = Column(String, nullable=True)
    
    # Company info
    company = Column(String, index=True)
    url = Column(String, nullable=True)
    company_size = Column(String, nullable=True)       # startup, sme, mid, enterprise
    sector = Column(String, nullable=True)              # industry sector
    employees = Column(String, nullable=True)           # count range
    annual_revenue = Column(String, nullable=True)      # revenue range
    hq_location = Column(String, nullable=True)         # country/region
    
    # AI system details
    ai_systems_count = Column(String, nullable=True)     # 0, 1-3, 4-10, 10+
    ai_system_names = Column(Text, nullable=True)        # comma-separated names
    ai_purpose = Column(Text, nullable=True)             # what AI does
    deployment_type = Column(String, nullable=True)      # internal, customer-facing, both
    data_sources = Column(Text, nullable=True)           # training data origin
    decision_type = Column(String, nullable=True)        # automated, human-in-loop, fully autonomous
    risk_self_assessment = Column(String, nullable=True) # low, limited, high, unacceptable
    
    # Technical details
    model_types = Column(Text, nullable=True)            # LLM, CNN, regression, etc.
    training_data_origin = Column(Text, nullable=True)   # where data comes from
    human_oversight = Column(Text, nullable=True)        # oversight mechanisms
    explainability = Column(Text, nullable=True)         # how AI explains decisions
    data_retention = Column(Text, nullable=True)         # data retention policy
    
    # Current compliance status
    has_documentation = Column(String, nullable=True)    # yes, no, partial
    dpo_appointed = Column(String, nullable=True)        # yes, no
    gdpr_compliant = Column(String, nullable=True)       # yes, no, in_progress
    existing_certifications = Column(Text, nullable=True) # ISO, SOC2, etc.
    previous_audits = Column(Text, nullable=True)        # audit history
    ce_marking = Column(String, nullable=True)           # yes, no, planned
    
    # High-risk categories
    risk_biometrics = Column(Boolean, default=False)
    risk_critical_infra = Column(Boolean, default=False)
    risk_education = Column(Boolean, default=False)
    risk_employment = Column(Boolean, default=False)
    risk_credit = Column(Boolean, default=False)
    risk_law_enforcement = Column(Boolean, default=False)
    risk_migration = Column(Boolean, default=False)
    risk_justice = Column(Boolean, default=False)
    risk_democratic = Column(Boolean, default=False)
    
    # Extra data as JSON
    additional_info = Column(Text, nullable=True)        # any extra JSON data
    
    # Description from old form
    description = Column(Text, nullable=True)
    
    # Language preference
    lang = Column(String, default="en")
    
    # Error message for debugging failed submissions
    error_message = Column(Text, nullable=True)
    
    def to_dict(self):
        """Convert submission to dict for prompt building."""
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        # Remove non-data fields
        for skip in ['id', 'status', 'created_at', 'report_path']:
            d.pop(skip, None)
        return d
    
    def risk_categories_active(self) -> list:
        """Get list of active high-risk categories."""
        categories = []
        mapping = {
            'risk_biometrics': 'Biometric identification (remote biometric identification systems)',
            'risk_critical_infra': 'Critical infrastructure management',
            'risk_education': 'Education and vocational training',
            'risk_employment': 'Employment, worker management, self-employment',
            'risk_credit': 'Credit assessment and access to essential services',
            'risk_law_enforcement': 'Law enforcement',
            'risk_migration': 'Migration, asylum, border control',
            'risk_justice': 'Administration of justice and democratic processes',
            'risk_democratic': 'Democratic processes (elections, democratic participation)',
        }
        for key, label in mapping.items():
            if getattr(self, key, False):
                categories.append(label)
        return categories
