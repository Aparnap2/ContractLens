-- Migration 004: Create contract_chunks table
-- Paragraph-sized chunks of contract text with clause family routing metadata.
-- Matches spec section 7.2.

CREATE TABLE IF NOT EXISTS contract_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  page_number INT NOT NULL,
  chunk_index INT NOT NULL,
  clause_family TEXT,
  chunk_text TEXT NOT NULL,
  chunk_hash TEXT NOT NULL,
  router_score NUMERIC(5,2),
  selected BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_contract_chunks_contract_id ON contract_chunks(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_chunks_clause_family ON contract_chunks(clause_family);
CREATE INDEX IF NOT EXISTS idx_contract_chunks_selected ON contract_chunks(contract_id, selected);
