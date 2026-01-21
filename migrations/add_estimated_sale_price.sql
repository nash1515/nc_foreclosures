-- Add estimated_sale_price column to cases table
-- Used for profit calculation: estimated_profit = estimated_sale_price - our_max_bid

ALTER TABLE cases ADD COLUMN IF NOT EXISTS estimated_sale_price DECIMAL(12, 2);

-- Add comment for clarity
COMMENT ON COLUMN cases.estimated_sale_price IS 'User-entered estimated sale price for profit calculation';
