"""SQLAlchemy ORM models for NC Foreclosures database."""

from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, DECIMAL, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Case(Base):
    """Main case information."""

    __tablename__ = 'cases'

    id = Column(Integer, primary_key=True)
    case_number = Column(String(50), unique=True, nullable=False)
    county_code = Column(String(10), nullable=False)
    county_name = Column(String(50), nullable=False)
    case_type = Column(String(100))
    case_status = Column(String(50))
    file_date = Column(Date)
    case_url = Column(Text)
    property_address = Column(Text)
    current_bid_amount = Column(DECIMAL(12, 2))
    next_bid_deadline = Column(TIMESTAMP)
    classification = Column(String(20))  # null, 'upcoming', 'upset_bid'
    last_scraped_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    events = relationship("CaseEvent", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    notes = relationship("UserNote", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Case(case_number='{self.case_number}', county='{self.county_name}')>"


class CaseEvent(Base):
    """Timeline of events within each case."""

    __tablename__ = 'case_events'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    event_date = Column(Date)
    event_type = Column(String(200))
    event_description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="events")

    def __repr__(self):
        return f"<CaseEvent(case_id={self.case_id}, type='{self.event_type}')>"


class Document(Base):
    """PDFs and extracted text."""

    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    document_name = Column(String(255))
    file_path = Column(Text)
    ocr_text = Column(Text)
    document_date = Column(Date)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="documents")

    def __repr__(self):
        return f"<Document(case_id={self.case_id}, name='{self.document_name}')>"


class ScrapeLog(Base):
    """Track scraping activity."""

    __tablename__ = 'scrape_logs'

    id = Column(Integer, primary_key=True)
    scrape_type = Column(String(20), nullable=False)  # 'initial' or 'daily'
    county_code = Column(String(10))
    start_date = Column(Date)
    end_date = Column(Date)
    cases_found = Column(Integer)
    cases_processed = Column(Integer)
    status = Column(String(20))  # 'success', 'failed', 'partial'
    error_message = Column(Text)
    started_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    completed_at = Column(TIMESTAMP)

    def __repr__(self):
        return f"<ScrapeLog(type='{self.scrape_type}', county='{self.county_code}', status='{self.status}')>"


class UserNote(Base):
    """Annotations from web app."""

    __tablename__ = 'user_notes'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    user_name = Column(String(100))
    note_text = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="notes")

    def __repr__(self):
        return f"<UserNote(case_id={self.case_id}, user='{self.user_name}')>"
