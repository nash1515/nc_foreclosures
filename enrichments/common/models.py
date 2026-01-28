"""SQLAlchemy models for enrichment data."""

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
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

    # Durham County RE
    durham_re_parcelpk = Column(String(20))
    durham_re_url = Column(Text)
    durham_re_enriched_at = Column(TIMESTAMP)
    durham_re_error = Column(Text)

    # Harnett County RE
    harnett_re_prid = Column(String(20))
    harnett_re_url = Column(Text)
    harnett_re_enriched_at = Column(TIMESTAMP)
    harnett_re_error = Column(Text)

    # Lee County RE
    lee_re_account_id = Column(String(30))
    lee_re_url = Column(Text)
    lee_re_enriched_at = Column(TIMESTAMP)
    lee_re_error = Column(Text)

    # Orange County RE
    orange_re_parcel_id = Column(String(20))
    orange_re_url = Column(Text)
    orange_re_enriched_at = Column(TIMESTAMP)
    orange_re_error = Column(Text)

    # Chatham County RE
    chatham_re_parcel_id = Column(String(20))
    chatham_re_url = Column(Text)
    chatham_re_enriched_at = Column(TIMESTAMP)
    chatham_re_error = Column(Text)

    # Future enrichments
    deed_url = Column(Text)
    deed_enriched_at = Column(TIMESTAMP)
    deed_error = Column(Text)

    property_info_url = Column(Text)
    property_info_enriched_at = Column(TIMESTAMP)
    property_info_error = Column(Text)

    zillow_url = Column(Text)
    zillow_zestimate = Column(Integer)
    zillow_price = Column(Integer)  # Sale/listing price (shown with "S" suffix when no zestimate)
    zillow_enriched_at = Column(TIMESTAMP)
    zillow_error = Column(Text)

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
    raw_results = Column(JSONB)
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
