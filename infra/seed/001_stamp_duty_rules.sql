-- Seed 001: Indian State-wise Stamp Duty Rules
-- These are reference rates used by the deterministic law engine (spec section 10.1)
-- for checking whether stamp duty on a given instrument is likely insufficient.
-- Based on common commercial lease/agreement stamp duty rates across Indian states.
-- Source: config-driven via stamp_rule_source tenant setting (spec section 11).

CREATE TABLE IF NOT EXISTS stamp_duty_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  state_name TEXT NOT NULL,
  instrument_type TEXT NOT NULL,
  duty_rate_pct NUMERIC(6,4) NOT NULL,
  max_exemption_inr NUMERIC(18,2) DEFAULT 0,
  min_duty_inr NUMERIC(18,2) DEFAULT 0,
  rule_source TEXT NOT NULL DEFAULT 'seed_table_v1',
  notes TEXT,
  UNIQUE(state_name, instrument_type)
);

INSERT INTO stamp_duty_rules (state_name, instrument_type, duty_rate_pct, max_exemption_inr, min_duty_inr, notes) VALUES
  ('Karnataka',     'LEASE',         0.1000, 10000000, 100, 'Commercial lease - 0.1% on average annual rent'),
  ('Karnataka',     'AGREEMENT',     0.0500, 5000000,  50,  'General agreement - 0.05% of consideration'),
  ('Karnataka',     'MSA',           0.0500, 5000000,  50,  'Master services agreement - treated as general agreement'),
  ('Karnataka',     'NDA',           0.0100, 0,        20,  'Non-disclosure agreement - fixed stamp'),
  ('Maharashtra',   'LEASE',         0.2500, 10000000, 200, 'Commercial lease - 0.25% on average annual rent'),
  ('Maharashtra',   'AGREEMENT',     0.1000, 5000000,  100, 'General agreement - 0.1% of consideration'),
  ('Maharashtra',   'MSA',           0.1000, 5000000,  100, 'Master services agreement'),
  ('Maharashtra',   'NDA',           0.0200, 0,        50,  'Non-disclosure agreement'),
  ('Tamil Nadu',    'LEASE',         1.0000, 20000000, 500, 'Commercial lease - 1% on average annual rent'),
  ('Tamil Nadu',    'AGREEMENT',     0.1000, 10000000, 100, 'General agreement'),
  ('Tamil Nadu',    'MSA',           0.1000, 10000000, 100, 'Master services agreement'),
  ('Tamil Nadu',    'NDA',           0.0100, 0,        30,  'Non-disclosure agreement'),
  ('Delhi',         'LEASE',         0.2000, 10000000, 200, 'Commercial lease - 0.2% on average annual rent'),
  ('Delhi',         'AGREEMENT',     0.0500, 5000000,  50,  'General agreement'),
  ('Delhi',         'MSA',           0.0500, 5000000,  50,  'Master services agreement'),
  ('Delhi',         'NDA',           0.0100, 0,        20,  'Non-disclosure agreement'),
  ('Uttar Pradesh', 'LEASE',         0.1500, 10000000, 200, 'Commercial lease'),
  ('Uttar Pradesh', 'AGREEMENT',     0.0500, 5000000,  50,  'General agreement'),
  ('Uttar Pradesh', 'MSA',           0.0500, 5000000,  50,  'Master services agreement'),
  ('Uttar Pradesh', 'NDA',           0.0100, 0,        20,  'Non-disclosure agreement'),
  ('Gujarat',       'LEASE',         0.1000, 10000000, 200, 'Commercial lease - 0.1% on average annual rent'),
  ('Gujarat',       'AGREEMENT',     0.1000, 5000000,  100, 'General agreement'),
  ('Gujarat',       'MSA',           0.1000, 5000000,  100, 'Master services agreement'),
  ('Gujarat',       'NDA',           0.0100, 0,        20,  'Non-disclosure agreement'),
  ('West Bengal',   'LEASE',         0.3000, 10000000, 300, 'Commercial lease - 0.3% on average annual rent'),
  ('West Bengal',   'AGREEMENT',     0.1000, 5000000,  100, 'General agreement'),
  ('West Bengal',   'MSA',           0.1000, 5000000,  100, 'Master services agreement'),
  ('West Bengal',   'NDA',           0.0200, 0,        50,  'Non-disclosure agreement'),
  ('Haryana',       'LEASE',         0.2000, 10000000, 200, 'Commercial lease'),
  ('Haryana',       'AGREEMENT',     0.0500, 5000000,  50,  'General agreement'),
  ('Haryana',       'MSA',           0.0500, 5000000,  50,  'Master services agreement'),
  ('Haryana',       'NDA',           0.0100, 0,        20,  'Non-disclosure agreement'),
  ('Telangana',     'LEASE',         0.5000, 10000000, 200, 'Commercial lease - 0.5% on average annual rent'),
  ('Telangana',     'AGREEMENT',     0.1000, 5000000,  100, 'General agreement'),
  ('Telangana',     'MSA',           0.1000, 5000000,  100, 'Master services agreement'),
  ('Telangana',     'NDA',           0.0100, 0,        20,  'Non-disclosure agreement')
ON CONFLICT (state_name, instrument_type) DO UPDATE SET
  duty_rate_pct = EXCLUDED.duty_rate_pct,
  max_exemption_inr = EXCLUDED.max_exemption_inr,
  min_duty_inr = EXCLUDED.min_duty_inr,
  rule_source = 'seed_table_v1';
