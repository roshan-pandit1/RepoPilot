-- Read-only point-in-time counts; zero does not prove workers have no in-memory tasks.
SELECT 'webhook_pending=' || count(*) FROM public.outbox_events WHERE status = 'pending'
UNION ALL SELECT 'sync_pending=' || count(*) FROM public.sync_jobs WHERE status = 'pending'
UNION ALL SELECT 'index_active=' || count(*) FROM public.index_jobs WHERE status IN ('pending', 'running')
UNION ALL SELECT 'embedding_active=' || count(*) FROM public.embedding_jobs WHERE status IN ('pending', 'running')
UNION ALL SELECT 'investigation_pending=' || count(*) FROM public.investigation_outbox WHERE status = 'pending'
UNION ALL SELECT 'report_pending=' || count(*) FROM public.investigation_report_outbox WHERE status = 'pending'
UNION ALL SELECT 'investigation_active=' || count(*) FROM public.investigation_jobs WHERE status IN ('queued', 'running')
UNION ALL SELECT 'report_active=' || count(*) FROM public.investigation_report_jobs WHERE status IN ('queued', 'running')
UNION ALL SELECT 'other_transactions=' || count(*) FROM pg_stat_activity
  WHERE datname = current_database() AND pid <> pg_backend_pid() AND xact_start IS NOT NULL;
