-- Migration 006: Create extraction_quotes table
-- Source-quote evidence backing each extracted field, with page anchors.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS extraction_quotes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  extraction_id UUID NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  source_quote TEXT NOT NULL,
  page_number INT NOT NULL,
  start_char INT,
  end_char INT
);

CREATE INDEX IF NOT EXISTS idx_extraction_quotes_extraction_id ON extraction_quotes(extraction_id);
CREATE INDEX IF NOT EXISTS idx_extraction_quotes_field_name ON extraction_quotes(extraction_id, field_name);
