-- Migration 013: Create exports table
-- Generated export packages (CSV/XLSX) for audit job results.
-- Referenced by GET /audit-jobs/{id}/exports/{export_id} endpoint.
-- Entity listed in spec section 7.1; DDL derived from spec patterns.

CREATE TABLE IF NOT EXISTS exports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_job_id UUID NOT NULL REFERENCES audit_jobs(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',
  format TEXT NOT NULL,
  storage_uri TEXT NOT NULL,
  file_size_bytes BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_exports_audit_job_id ON exports(audit_job_id);
CREATE INDEX IF NOT EXISTS idx_exports_status ON exports(status);
