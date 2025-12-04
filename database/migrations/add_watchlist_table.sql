-- Watchlist table for user's starred cases
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, case_id)
);

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist(user_id);
-- Index for fast lookups by case
CREATE INDEX IF NOT EXISTS idx_watchlist_case_id ON watchlist(case_id);
