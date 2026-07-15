-- Migration 010: Create human_reviews table
-- Human-in-the-loop review records for ambiguous or low-confidence extractions.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS human_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  review_type TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt_json JSONB NOT NULL,
  resolution_json JSONB,
  reviewer_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_human_reviews_contract_id ON human_reviews(contract_id);
CREATE INDEX IF NOT EXISTS idx_human_reviews_status ON human_reviews(status);
