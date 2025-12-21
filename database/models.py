"""SQLAlchemy ORM models for NC Foreclosures database."""

from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, DECIMAL, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """Users authenticated via Google OAuth."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255))
    avatar_url = Column(Text)
    role = Column(String(20), nullable=False, default='user')  # 'admin' or 'user'
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_login_at = Column(TIMESTAMP)

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}')>"


class Watchlist(Base):
    """User's starred/watchlisted cases."""

    __tablename__ = 'watchlist'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User")
    case = relationship("Case")

    def __repr__(self):
        return f"<Watchlist(user_id={self.user_id}, case_id={self.case_id})>"


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
    style = Column(Text)  # Full case title (e.g., "FORECLOSURE (HOA) - Mark Dwayne Ellis")
    property_address = Column(Text)
    parcel_id = Column(String(20))  # County parcel/PIN number (10-digit for Wake County)
    current_bid_amount = Column(DECIMAL(12, 2))
    minimum_next_bid = Column(DECIMAL(12, 2))  # NC law: current_bid * 1.05
    next_bid_deadline = Column(TIMESTAMP)
    classification = Column(String(20))  # 'upcoming', 'upset_bid', 'blocked', 'closed_sold', 'closed_dismissed'
    sale_date = Column(Date)
    legal_description = Column(Text)
    trustee_name = Column(String(255))
    attorney_name = Column(String(255))
    attorney_phone = Column(String(50))
    attorney_email = Column(String(255))

    # Collaboration fields (Phase 3)
    our_initial_bid = Column(DECIMAL(12, 2))
    our_second_bid = Column(DECIMAL(12, 2))
    our_max_bid = Column(DECIMAL(12, 2))
    team_notes = Column(Text)

    reviewed_at = Column(TIMESTAMP)
    last_scraped_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    events = relationship("CaseEvent", back_populates="case", cascade="all, delete-orphan")
    parties = relationship("Party", back_populates="case", cascade="all, delete-orphan")
    hearings = relationship("Hearing", back_populates="case", cascade="all, delete-orphan")
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
    filed_by = Column(Text)  # Party who filed the event
    filed_against = Column(Text)  # Party the event is against
    hearing_date = Column(TIMESTAMP)  # If event has associated hearing
    document_url = Column(Text)  # URL to associated document (for Phase 2)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="events")

    def __repr__(self):
        return f"<CaseEvent(case_id={self.case_id}, type='{self.event_type}')>"


class Party(Base):
    """People/entities involved in each case."""

    __tablename__ = 'parties'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    party_type = Column(String(50), nullable=False)  # 'Respondent', 'Petitioner', 'Trustee', etc.
    party_name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="parties")

    def __repr__(self):
        return f"<Party(case_id={self.case_id}, type='{self.party_type}', name='{self.party_name}')>"


class Hearing(Base):
    """Scheduled hearings for each case."""

    __tablename__ = 'hearings'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    hearing_date = Column(Date)
    hearing_time = Column(String(20))  # Store as string for flexibility
    hearing_type = Column(String(100))  # 'Hearing Before the Clerk', etc.
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="hearings")

    def __repr__(self):
        return f"<Hearing(case_id={self.case_id}, type='{self.hearing_type}', date='{self.hearing_date}')>"


class Document(Base):
    """PDFs and extracted text."""

    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    event_id = Column(Integer, ForeignKey('case_events.id', ondelete='SET NULL'), nullable=True)
    document_name = Column(String(255))
    file_path = Column(Text)
    ocr_text = Column(Text)
    document_date = Column(Date)
    extraction_attempted_at = Column(TIMESTAMP)  # When extraction was last attempted
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    case = relationship("Case", back_populates="documents")
    event = relationship("CaseEvent")

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
    acknowledged_at = Column(TIMESTAMP)  # When user acknowledged a failed scrape

    tasks = relationship('ScrapeLogTask', back_populates='scrape_log', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ScrapeLog(type='{self.scrape_type}', county='{self.county_code}', status='{self.status}')>"


class ScrapeLogTask(Base):
    """Track individual tasks within a scrape operation."""

    __tablename__ = 'scrape_log_tasks'

    id = Column(Integer, primary_key=True)
    scrape_log_id = Column(Integer, ForeignKey('scrape_logs.id', ondelete='CASCADE'))
    task_name = Column(String(50), nullable=False)
    task_order = Column(Integer)
    items_checked = Column(Integer)
    items_found = Column(Integer)
    items_processed = Column(Integer)
    started_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    completed_at = Column(TIMESTAMP)
    status = Column(String(20))
    error_message = Column(Text)

    scrape_log = relationship('ScrapeLog', back_populates='tasks')

    def __repr__(self):
        return f"<ScrapeLogTask(name='{self.task_name}', status='{self.status}')>"


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


class SchedulerConfig(Base):
    """Configuration for scheduled jobs (editable via frontend)."""

    __tablename__ = 'scheduler_config'

    id = Column(Integer, primary_key=True)
    job_name = Column(String(50), unique=True, nullable=False)
    schedule_hour = Column(Integer, nullable=False, default=5)
    schedule_minute = Column(Integer, nullable=False, default=0)
    days_of_week = Column(String(20), nullable=False, default='mon,tue,wed,thu,fri')
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(TIMESTAMP)
    last_run_status = Column(String(20))
    last_run_message = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    def __repr__(self):
        return f"<SchedulerConfig(job='{self.job_name}', hour={self.schedule_hour}, enabled={self.enabled})>"


class SkippedCase(Base):
    """Cases examined but not saved during daily scrape - for review."""

    __tablename__ = 'skipped_cases'

    id = Column(Integer, primary_key=True)
    case_number = Column(String(50), nullable=False)
    county_code = Column(String(10), nullable=False)
    county_name = Column(String(50), nullable=False)
    case_url = Column(Text)
    case_type = Column(String(100))
    style = Column(Text)
    file_date = Column(Date)
    events_json = Column(JSONB)  # JSONB: auto-deserializes to Python list
    skip_reason = Column(String(255))
    scrape_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    reviewed_at = Column(TIMESTAMP)
    review_action = Column(String(20))  # 'added', 'dismissed', NULL (pending)

    def __repr__(self):
        return f"<SkippedCase(case_number='{self.case_number}', scrape_date='{self.scrape_date}')>"


class CaseAnalysis(Base):
    """AI analysis results for upset_bid cases."""
    __tablename__ = 'case_analyses'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Analysis outputs
    summary = Column(Text)  # Legacy - kept for backward compatibility
    comprehensive_analysis = Column(JSONB)  # New 5-section analysis structure
    financials = Column(JSONB)
    red_flags = Column(JSONB)
    defendant_name = Column(String(255))
    deed_book = Column(String(50))
    deed_page = Column(String(50))

    # Discrepancy tracking
    discrepancies = Column(JSONB)

    # Document contribution tracking
    document_contributions = Column(JSONB)

    # Metadata
    status = Column(String(20), nullable=False, default='pending')
    model_used = Column(String(50))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost_cents = Column(Integer)
    requested_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    completed_at = Column(TIMESTAMP)
    error_message = Column(Text)

    # Relationship
    case = relationship("Case", backref="analysis")

    def __repr__(self):
        return f"<CaseAnalysis(case_id={self.case_id}, status={self.status})>"
