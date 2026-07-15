-- Migration 005: Create extractions table
-- LLM extraction attempts for a contract, versioned and provider-tracked.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS extractions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  schema_version TEXT NOT NULL,
  provider_name TEXT NOT NULL,
  model_name TEXT NOT NULL,
  attempt_no INT NOT NULL,
  confidence NUMERIC(5,2),
  structured_json JSONB NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_extractions_contract_id ON extractions(contract_id);
CREATE INDEX IF NOT EXISTS idx_extractions_status ON extractions(status);
