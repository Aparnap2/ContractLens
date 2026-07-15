-- ContractLens: Default Tenant Configuration
-- =============================================
-- Corresponds to master_spec.md §11 (Configuration model).
-- Phase A: single-tenant — a single settings row.
-- Phase B: replaced by a real tenant_settings table with per-tenant rows.
--
-- Seed number 003 — runs after tables are created by migrations.

-- The tenant_settings table must already exist (created in migration 002).
-- If this is a fresh database, the INSERT will create the default row.
-- If re-seeding, use ON CONFLICT to upsert rather than duplicate.

INSERT INTO tenant_settings (
    id,
    client_hub_city,
    closing_date,
    ld_high_threshold_inr,
    renewal_escalation_threshold_pct,
    confidence_threshold,
    max_provider_retries,
    allow_semantic_routing,
    allow_auto_ticket_creation,
    allow_auto_email_drafts,
    stamp_rule_source,
    created_at,
    updated_at
)
VALUES (
    '00000000-0000-0000-0000-000000000000',  -- single default tenant UUID
    'Bengaluru',                               -- §11: client_hub_city
    '2026-09-15',                              -- §11: closing_date
    5000000.00,                                -- §11: ld_high_threshold_inr (₹5M)
    15,                                        -- §11: renewal_escalation_threshold_pct (%)
    0.78,                                      -- §11: confidence_threshold
    3,                                         -- §11: max_provider_retries
    FALSE,                                     -- §11: allow_semantic_routing (disabled in A)
    TRUE,                                      -- §11: allow_auto_ticket_creation
    TRUE,                                      -- §11: allow_auto_email_drafts
    'seed_table_v1',                           -- §11: stamp_rule_source
    NOW(),                                     -- created_at
    NOW()                                      -- updated_at
)
ON CONFLICT (id) DO UPDATE SET
    client_hub_city               = EXCLUDED.client_hub_city,
    closing_date                  = EXCLUDED.closing_date,
    ld_high_threshold_inr         = EXCLUDED.ld_high_threshold_inr,
    renewal_escalation_threshold_pct = EXCLUDED.renewal_escalation_threshold_pct,
    confidence_threshold          = EXCLUDED.confidence_threshold,
    max_provider_retries          = EXCLUDED.max_provider_retries,
    allow_semantic_routing        = EXCLUDED.allow_semantic_routing,
    allow_auto_ticket_creation    = EXCLUDED.allow_auto_ticket_creation,
    allow_auto_email_drafts       = EXCLUDED.allow_auto_email_drafts,
    stamp_rule_source             = EXCLUDED.stamp_rule_source,
    updated_at                    = NOW()
;

-- Verify
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tenant_settings WHERE id = '00000000-0000-0000-0000-000000000000') THEN
        RAISE EXCEPTION 'Default tenant settings row was not inserted — check tenant_settings table schema.';
    END IF;
END $$;
