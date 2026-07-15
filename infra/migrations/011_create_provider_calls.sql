-- Migration 011: Create provider_calls table
-- Audit trail for every LLM provider invocation (success/failure metrics).
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS provider_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_job_id UUID NOT NULL REFERENCES audit_jobs(id) ON DELETE CASCADE,
  contract_id UUID REFERENCES contracts(id) ON DELETE SET NULL,
  provider_name TEXT NOT NULL,
  model_name TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  response_hash TEXT,
  latency_ms INT,
  success BOOLEAN NOT NULL,
  tokens_in INT,
  tokens_out INT,
  error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_provider_calls_audit_job_id ON provider_calls(audit_job_id);
CREATE INDEX IF NOT EXISTS idx_provider_calls_provider ON provider_calls(provider_name);
CREATE INDEX IF NOT EXISTS idx_provider_calls_success ON provider_calls(audit_job_id, success);
