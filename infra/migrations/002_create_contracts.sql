-- Migration 002: Create contracts table
-- Each uploaded contract document within an audit job.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS contracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_job_id UUID NOT NULL REFERENCES audit_jobs(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  file_hash TEXT NOT NULL,
  storage_uri TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  parser_used TEXT,
  parser_quality_score NUMERIC(5,2),
  contract_type TEXT,
  vendor_name TEXT,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_filehash_per_job ON contracts(audit_job_id, file_hash);
CREATE INDEX IF NOT EXISTS idx_contracts_audit_job_id ON contracts(audit_job_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
