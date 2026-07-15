-- Migration 009: Create action_items table
-- Remediation actions (ticket drafts, email drafts) with idempotency keys.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS action_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  action_type TEXT NOT NULL,
  external_system TEXT,
  idempotency_key TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  status TEXT NOT NULL,
  external_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_action_idempotency_key ON action_items(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_action_items_contract_id ON action_items(contract_id);
CREATE INDEX IF NOT EXISTS idx_action_items_status ON action_items(status);
