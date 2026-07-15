-- Migration 007: Create legal_findings table
-- Deterministic legal rule outputs: stamp duty, CoC, deadline breach, etc.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS legal_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  finding_code TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  statute_reference TEXT,
  financial_impact_inr NUMERIC(18,2),
  deterministic BOOLEAN NOT NULL DEFAULT TRUE,
  evidence_json JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_legal_findings_contract_id ON legal_findings(contract_id);
CREATE INDEX IF NOT EXISTS idx_legal_findings_severity ON legal_findings(severity);
CREATE INDEX IF NOT EXISTS idx_legal_findings_code ON legal_findings(finding_code);
