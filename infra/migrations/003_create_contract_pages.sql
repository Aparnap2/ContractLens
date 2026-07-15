-- Migration 003: Create contract_pages table
-- Per-page extracted text from contract PDFs, with OCR fallback tracking.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS contract_pages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  page_number INT NOT NULL,
  extracted_text TEXT NOT NULL,
  ocr_used BOOLEAN NOT NULL DEFAULT FALSE,
  text_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contract_pages_contract_id ON contract_pages(contract_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_page_number ON contract_pages(contract_id, page_number);
