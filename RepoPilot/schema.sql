-- RepoPilot reference schema, PostgreSQL 16+ with pgvector.
-- Use Alembic migrations in the application; do not execute blindly against a live DB.
-- Embedding dimension 1536 assumes a compatible embedding model; change in a versioned migration.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE app_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_user_id BIGINT NOT NULL UNIQUE,
  github_login TEXT NOT NULL,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_account_id BIGINT NOT NULL UNIQUE,
  account_login TEXT NOT NULL,
  account_type TEXT NOT NULL CHECK (account_type IN ('User','Organization')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenant_memberships (
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner','maintainer','viewer')),
  last_verified_at TIMESTAMPTZ,
  PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE github_installations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  github_installation_id BIGINT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','removed')),
  installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE repositories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  installation_id UUID NOT NULL REFERENCES github_installations(id) ON DELETE CASCADE,
  github_repository_id BIGINT NOT NULL UNIQUE,
  owner_login TEXT NOT NULL,
  name TEXT NOT NULL,
  default_branch TEXT NOT NULL,
  visibility TEXT NOT NULL CHECK (visibility IN ('public','private','internal')),
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  latest_indexed_sha TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(id, tenant_id)
);
CREATE INDEX repositories_tenant_idx ON repositories(tenant_id);

CREATE TABLE issues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  github_issue_id BIGINT NOT NULL,
  issue_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  state TEXT NOT NULL CHECK (state IN ('open','closed')),
  source_updated_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(repository_id, issue_number),
  UNIQUE(repository_id, github_issue_id)
);
CREATE INDEX issues_repo_date_idx ON issues(repository_id, source_updated_at DESC);

CREATE TABLE webhook_deliveries (
  delivery_id UUID PRIMARY KEY, -- X-GitHub-Delivery, same on redelivery
  event_type TEXT NOT NULL,
  event_action TEXT,
  payload_sha256 TEXT NOT NULL,
  tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received','processed','ignored','failed')),
  last_error_code TEXT
);

CREATE TABLE outbox_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  entity_id UUID,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX outbox_unpublished_idx ON outbox_events(next_attempt_at) WHERE published_at IS NULL;

CREATE TABLE repository_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  commit_sha TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  index_status TEXT NOT NULL CHECK (index_status IN ('queued','indexing','ready','failed')),
  indexed_at TIMESTAMPTZ,
  UNIQUE(repository_id, commit_sha, embedding_model)
);

CREATE TABLE code_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  snapshot_id UUID NOT NULL REFERENCES repository_snapshots(id) ON DELETE CASCADE,
  relative_path TEXT NOT NULL,
  language TEXT,
  start_line INTEGER NOT NULL CHECK (start_line > 0),
  end_line INTEGER NOT NULL CHECK (end_line >= start_line),
  content TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  embedding vector(1536),
  search_document TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  UNIQUE(snapshot_id, relative_path, start_line, end_line)
);
CREATE INDEX code_chunks_snapshot_idx ON code_chunks(snapshot_id, relative_path);
CREATE INDEX code_chunks_fts_idx ON code_chunks USING GIN(search_document);
-- Enable only after measuring dataset size, recall, and tenant-filter selectivity:
-- CREATE INDEX CONCURRENTLY code_chunks_embedding_hnsw_idx
--   ON code_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE investigations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
  snapshot_id UUID REFERENCES repository_snapshots(id) ON DELETE SET NULL,
  requested_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  idempotency_key TEXT,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','insufficient_evidence','failed','canceled')),
  model_id TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  result_json JSONB,
  error_code TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, idempotency_key)
);
CREATE INDEX investigations_issue_idx ON investigations(issue_id, created_at DESC);

CREATE TABLE investigation_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  chunk_id UUID REFERENCES code_chunks(id) ON DELETE SET NULL,
  source_kind TEXT NOT NULL CHECK (source_kind IN ('code','issue','pull_request','documentation')),
  path TEXT,
  start_line INTEGER,
  end_line INTEGER,
  source_sha TEXT,
  github_url TEXT NOT NULL,
  quoted_excerpt TEXT,
  relevance_score DOUBLE PRECISION,
  cited_claim TEXT
);
CREATE INDEX investigation_evidence_lookup ON investigation_evidence(investigation_id);

CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  graph_thread_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('running','interrupted','completed','failed')),
  input_tokens BIGINT NOT NULL DEFAULT 0,
  output_tokens BIGINT NOT NULL DEFAULT 0,
  cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE agent_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  step_name TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL,
  duration_ms INTEGER,
  sanitized_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  base_sha TEXT NOT NULL,
  patch_text TEXT NOT NULL,
  regression_test_plan TEXT,
  status TEXT NOT NULL CHECK (status IN ('draft','awaiting_approval','approved','rejected','published','expired')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE proposal_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  actor_user_id UUID NOT NULL REFERENCES app_users(id),
  decision TEXT NOT NULL CHECK (decision IN ('approve','reject')),
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pull_request_publications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  proposal_id UUID NOT NULL UNIQUE REFERENCES proposals(id) ON DELETE CASCADE,
  github_pr_number INTEGER NOT NULL,
  github_pr_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id),
  verdict TEXT NOT NULL CHECK (verdict IN ('helpful','incorrect','incomplete')),
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(investigation_id, user_id)
);

CREATE TABLE usage_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  investigation_id UUID REFERENCES investigations(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
  duration_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX usage_events_tenant_time_idx ON usage_events(tenant_id, created_at DESC);

CREATE TABLE evaluation_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_version TEXT NOT NULL,
  repo_fingerprint TEXT NOT NULL,
  fixture_json JSONB NOT NULL,
  expected_json JSONB NOT NULL,
  split TEXT NOT NULL CHECK (split IN ('dev','test')),
  UNIQUE(dataset_version, repo_fingerprint)
);
CREATE TABLE evaluation_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES evaluation_cases(id),
  run_version TEXT NOT NULL,
  scores JSONB NOT NULL,
  failure_category TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(case_id, run_version)
);

CREATE TABLE audit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  actor_user_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_tenant_time_idx ON audit_events(tenant_id, occurred_at DESC);

-- Row security: access is denied by default if app.tenant_id is missing.
-- The actual runtime role must not own tables or have BYPASSRLS privileges.
-- Set tenant ID only after validated authentication + authorization, with SET LOCAL
-- inside each DB transaction; workers must also bind the correct tenant.
CREATE SCHEMA IF NOT EXISTS app;
CREATE OR REPLACE FUNCTION app.current_tenant() RETURNS UUID
  LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
$$;
DO $$
DECLARE tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'github_installations','repositories','issues','repository_snapshots',
    'code_chunks','investigations','investigation_evidence','agent_runs',
    'agent_steps','proposals','proposal_decisions','pull_request_publications',
    'feedback','usage_events','audit_events'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant())',tbl
    );
  END LOOP;
END $$;
-- Tenant, user, membership, webhook, and outbox tables require separate tightly
-- controlled ingestion/admin policies and DB roles. Never expose through generic tenant queries.
