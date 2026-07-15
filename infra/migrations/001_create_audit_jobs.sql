-- Migration 001: Create audit_jobs table
-- Core entity representing a due diligence audit engagement.
-- Matches spec section 7.2.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS audit_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  closing_date DATE,
  client_hub_city TEXT,
  total_contracts INT NOT NULL DEFAULT 0,
  processed_contracts INT NOT NULL DEFAULT 0,
  aggregate_exposure_inr NUMERIC(18,2) NOT NULL DEFAULT 0,
  summary_json JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_jobs_status ON audit_jobs(status);
CREATE INDEX IF NOT EXISTS idx_audit_jobs_created_at ON audit_jobs(created_at);
