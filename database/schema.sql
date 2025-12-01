-- NC Foreclosures Database Schema
-- PostgreSQL 16+

-- Cases table - Main case information
CREATE TABLE IF NOT EXISTS cases (
    id SERIAL PRIMARY KEY,
    case_number VARCHAR(50) UNIQUE NOT NULL,
    county_code VARCHAR(10) NOT NULL,
    county_name VARCHAR(50) NOT NULL,
    case_type VARCHAR(100),
    case_status VARCHAR(50),
    file_date DATE,
    case_url TEXT,
    style TEXT,  -- Full case title (e.g., "FORECLOSURE (HOA) - Mark Dwayne Ellis")
    property_address TEXT,
    current_bid_amount DECIMAL(12, 2),
    next_bid_deadline TIMESTAMP,
    classification VARCHAR(20), -- null, 'upcoming', 'upset_bid'
    sale_date DATE,
    legal_description TEXT,
    trustee_name VARCHAR(255),
    attorney_name VARCHAR(255),
    attorney_phone VARCHAR(50),
    attorney_email VARCHAR(255),
    last_scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Case events table - Timeline of events within each case
CREATE TABLE IF NOT EXISTS case_events (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    event_date DATE,
    event_type VARCHAR(200),
    event_description TEXT,
    filed_by TEXT,  -- Party who filed the event
    filed_against TEXT,  -- Party the event is against
    hearing_date TIMESTAMP,  -- If event has associated hearing
    document_url TEXT,  -- URL to associated document (for Phase 2)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parties table - People/entities involved in each case
CREATE TABLE IF NOT EXISTS parties (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    party_type VARCHAR(50) NOT NULL,  -- 'Respondent', 'Petitioner', 'Trustee', etc.
    party_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hearings table - Scheduled hearings for each case
CREATE TABLE IF NOT EXISTS hearings (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    hearing_date DATE,
    hearing_time TIME,
    hearing_type VARCHAR(100),  -- 'Hearing Before the Clerk', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents table - PDFs and extracted text
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_name VARCHAR(255),
    file_path TEXT,
    ocr_text TEXT,
    document_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scrape logs table - Track scraping activity
CREATE TABLE IF NOT EXISTS scrape_logs (
    id SERIAL PRIMARY KEY,
    scrape_type VARCHAR(20) NOT NULL, -- 'initial' or 'daily'
    county_code VARCHAR(10),
    start_date DATE,
    end_date DATE,
    cases_found INTEGER,
    cases_processed INTEGER,
    status VARCHAR(20), -- 'success', 'failed', 'partial'
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- User notes table - Annotations from web app
CREATE TABLE IF NOT EXISTS user_notes (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    user_name VARCHAR(100),
    note_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_cases_county_code ON cases(county_code);
CREATE INDEX IF NOT EXISTS idx_cases_classification ON cases(classification);
CREATE INDEX IF NOT EXISTS idx_cases_file_date ON cases(file_date);
CREATE INDEX IF NOT EXISTS idx_case_events_case_id ON case_events(case_id);
CREATE INDEX IF NOT EXISTS idx_parties_case_id ON parties(case_id);
CREATE INDEX IF NOT EXISTS idx_hearings_case_id ON hearings(case_id);
CREATE INDEX IF NOT EXISTS idx_documents_case_id ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_user_notes_case_id ON user_notes(case_id);

-- Full-text search index on OCR text
CREATE INDEX IF NOT EXISTS idx_documents_ocr_text ON documents USING GIN(to_tsvector('english', COALESCE(ocr_text, '')));

-- AI Analysis table - Stores Claude analysis results
CREATE TABLE IF NOT EXISTS ai_analysis (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(50),

    -- Status verification
    is_valid_upset_bid BOOLEAN,
    status_blockers JSONB,
    recommended_classification VARCHAR(50),

    -- Deadline info
    upset_deadline DATE,
    deadline_extended BOOLEAN,
    extension_count INTEGER DEFAULT 0,

    -- Financial summary
    current_bid_amount DECIMAL(12,2),
    estimated_total_liens DECIMAL(12,2),
    mortgage_info JSONB,
    tax_info JSONB,

    -- Research flags
    research_flags JSONB,

    -- Document usefulness tracking
    document_evaluations JSONB,

    -- Free-form
    analysis_notes TEXT,
    confidence_score DECIMAL(3,2),
    discrepancies JSONB,

    -- Audit
    tokens_used INTEGER,
    cost_estimate DECIMAL(8,4)
);

CREATE INDEX IF NOT EXISTS idx_ai_analysis_case_id ON ai_analysis(case_id);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_analyzed_at ON ai_analysis(analyzed_at);

-- Document Skip Patterns table - Learned patterns for skipping useless documents
CREATE TABLE IF NOT EXISTS document_skip_patterns (
    id SERIAL PRIMARY KEY,
    pattern VARCHAR(255) NOT NULL UNIQUE,
    pattern_type VARCHAR(50) DEFAULT 'learned',
    skip_count INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_document_skip_patterns_pattern ON document_skip_patterns(pattern);
