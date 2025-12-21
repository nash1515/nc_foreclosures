"""SQLAlchemy models for enrichment data."""

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.models import Base


class Enrichment(Base):
    """Stores enrichment URLs and metadata for cases."""

    __tablename__ = 'enrichments'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), unique=True, nullable=False)

    # Wake County RE
    wake_re_account = Column(String(20))
    wake_re_url = Column(Text)
    wake_re_enriched_at = Column(TIMESTAMP)
    wake_re_error = Column(Text)

    # Future enrichments
    propwire_url = Column(Text)
    propwire_enriched_at = Column(TIMESTAMP)
    propwire_error = Column(Text)

    deed_url = Column(Text)
    deed_enriched_at = Column(TIMESTAMP)
    deed_error = Column(Text)

    property_info_url = Column(Text)
    property_info_enriched_at = Column(TIMESTAMP)
    property_info_error = Column(Text)

    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationship
    case = relationship('Case', backref='enrichment', uselist=False)

    def __repr__(self):
        return f"<Enrichment case_id={self.case_id} wake_re={bool(self.wake_re_url)}>"


class EnrichmentReviewLog(Base):
    """Logs enrichment attempts requiring manual review (0 or 2+ matches)."""

    __tablename__ = 'enrichment_review_log'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    enrichment_type = Column(String(50), nullable=False)
    search_method = Column(String(20), nullable=False)
    search_value = Column(Text, nullable=False)
    matches_found = Column(Integer, nullable=False)
    raw_results = Column(JSON)
    resolution_notes = Column(Text)
    resolved_at = Column(TIMESTAMP)
    resolved_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    case = relationship('Case', backref='enrichment_reviews')
    resolver = relationship('User', foreign_keys=[resolved_by])

    def __repr__(self):
        status = 'resolved' if self.resolved_at else 'pending'
        return f"<EnrichmentReviewLog id={self.id} type={self.enrichment_type} status={status}>"
