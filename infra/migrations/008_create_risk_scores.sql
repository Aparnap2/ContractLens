-- Migration 008: Create risk_scores table
-- Computed risk score per contract with weighted breakdown.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS risk_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  total_score NUMERIC(6,2) NOT NULL,
  level TEXT NOT NULL,
  exposure_inr NUMERIC(18,2) NOT NULL DEFAULT 0,
  scoring_breakdown JSONB NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_risk_scores_contract_id ON risk_scores(contract_id);
CREATE INDEX IF NOT EXISTS idx_risk_scores_level ON risk_scores(level);
