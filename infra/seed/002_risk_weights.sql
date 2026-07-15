-- Seed 002: Default Risk Weights
-- Risk score weighting factors from spec section 10.7.
-- All thresholds are config-driven per spec section 11.
-- This seed establishes defaults that can be overridden via tenant_settings.

CREATE TABLE IF NOT EXISTS risk_weights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_code TEXT NOT NULL UNIQUE,
  weight INT NOT NULL,
  description TEXT NOT NULL,
  risk_level_thresholds JSONB NOT NULL DEFAULT '{"info": 9, "low": 29, "medium": 49, "high": 69, "critical": 999}',
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO risk_weights (finding_code, weight, description) VALUES
  ('INSUFFICIENT_STAMP',     30, 'Insufficient stamp duty under Section 35 - evidence inadmissibility risk'),
  ('DEADLINE_BREACH',        25, 'Termination notice period exceeds days until closing'),
  ('CHANGE_OF_CONTROL',      20, 'Change-of-control clause with penalty or consent requirement'),
  ('HIGH_LD',                15, 'Liquidated damages amount exceeds configured threshold'),
  ('AUTO_RENEW_ESCALATION',  10, 'Automatic renewal with price escalation above threshold'),
  ('DISTANT_VENUE',          5,  'Arbitration/jurisdiction city differs from client hub city'),
  ('UNCCAPED_CONSEQUENTIAL', 5,  'Consequential damages not capped or waived')
ON CONFLICT (finding_code) DO UPDATE SET
  weight = EXCLUDED.weight,
  description = EXCLUDED.description;
