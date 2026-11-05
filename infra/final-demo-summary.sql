-- Read-only, non-secret logical metadata for backup/restore comparison at revision 0013.
SELECT json_build_object(
  'revision', (SELECT string_agg(version_num, ',' ORDER BY version_num) FROM public.alembic_version),
  'repositories', (SELECT count(*) FROM public.repositories),
  'installations', (SELECT count(*) FROM public.installations),
  'memberships', (SELECT count(*) FROM public.memberships),
  'sessions', (SELECT count(*) FROM public.auth_sessions),
  'issues', (SELECT count(*) FROM public.issues),
  'snapshots', (SELECT count(*) FROM public.code_snapshots),
  'files', (SELECT count(*) FROM public.indexed_files),
  'chunks', (SELECT count(*) FROM public.code_chunks),
  'investigations', (SELECT count(*) FROM public.investigation_jobs),
  'evidence', (SELECT count(*) FROM public.investigation_evidence),
  'report_jobs', (SELECT count(*) FROM public.investigation_report_jobs),
  'reports', (SELECT count(*) FROM public.investigation_reports),
  'target_repository', (SELECT count(*) FROM public.repositories WHERE id = 1435878031),
  'target_issue_1', (SELECT count(*) FROM public.issues WHERE repository_id = 1435878031 AND number = 1),
  'target_snapshots', (SELECT COALESCE(json_agg(json_build_object(
      'id', id, 'commit', commit_sha, 'published', published,
      'files', file_count, 'chunks', chunk_count, 'skipped', skipped_count) ORDER BY id), '[]'::json)
    FROM public.code_snapshots WHERE repository_id = 1435878031),
  'target_jobs', (SELECT COALESCE(json_agg(json_build_object(
      'id', id, 'status', status, 'snapshot_id', snapshot_id, 'commit', snapshot_commit_sha) ORDER BY id), '[]'::json)
    FROM public.investigation_jobs WHERE repository_id = 1435878031),
  'target_reports', (SELECT COALESCE(json_agg(json_build_object(
      'id', id, 'investigation_id', investigation_id, 'snapshot_id', snapshot_id,
      'commit', commit_sha, 'provider', provider) ORDER BY id), '[]'::json)
    FROM public.investigation_reports WHERE repository_id = 1435878031)
);
