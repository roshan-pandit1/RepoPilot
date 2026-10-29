#!/bin/bash
# Read-only host verification for an already approved 4D report task; do not run against production.
set -euo pipefail
report_job="${1:-}"
[[ "$report_job" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || {
  printf 'Supply the lowercase report job UUID.\n' >&2; exit 1;
}
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
docker compose exec -T postgres sh -c '
  [ "$POSTGRES_DB" = repopilot ] || exit 1
  exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v job_id="$1"
' _ "$report_job" <<'SQL'
SELECT j.id, j.investigation_id, j.repository_id, j.status, j.attempts, j.error_code,
       j.snapshot_id, r.id AS report_id, r.commit_sha, r.provider, r.model,
       o.status AS outbox_status, o.attempts AS dispatch_attempts,
       (SELECT count(*) FROM investigation_reports x WHERE x.report_job_id=j.id) AS report_count
FROM investigation_report_jobs j
JOIN investigation_report_outbox o ON o.job_id=j.id AND o.repository_id=j.repository_id AND o.tenant_id=j.tenant_id
LEFT JOIN investigation_reports r ON r.report_job_id=j.id AND r.investigation_id=j.investigation_id
  AND r.snapshot_id=j.snapshot_id AND r.repository_id=j.repository_id AND r.tenant_id=j.tenant_id
WHERE j.id=:'job_id' AND j.repository_id=1435878031
  AND j.investigation_id='457d40bf-7e15-4e10-9a27-b8a0de9e513b';
SQL
# Validate report references and ownership against the actual persisted 4C evidence, without
# printing issue text, source, model output, connection details or credentials.
docker compose exec -T api python - "$report_job" <<'PY'
import json, sys
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.domain.models import CodeSnapshot, InvestigationJob, InvestigationReport, InvestigationReportJob, InvestigationReportOutbox
from app.modules.investigation.reporting import evidence_inputs, render_report_payload
try:
    settings = get_settings()
    url = make_url(settings.database_url)
    assert settings.app_env == 'development' and url.get_backend_name() == 'postgresql'
    assert url.host == 'postgres' and url.database == 'repopilot'
    assert settings.embedding_provider in ('disabled', 'fake') and not settings.embedding_allow_paid
    with Session(create_engine(url, hide_parameters=True)) as db:
        task = db.get(InvestigationReportJob, sys.argv[1])
        assert task and task.investigation_id == '457d40bf-7e15-4e10-9a27-b8a0de9e513b'
        assert task.repository_id == 1435878031 and task.status == 'completed' and task.attempts >= 1
        parent = db.get(InvestigationJob, task.investigation_id)
        assert parent and parent.status == 'completed' and parent.attempts == 1 and parent.operation == 'code_evidence'
        assert parent.repository_id == task.repository_id and parent.tenant_id == task.tenant_id
        assert parent.user_id == task.user_id and parent.snapshot_id == task.snapshot_id
        assert parent.snapshot_id == '24e51533-c612-4833-921d-447cfed7df99'
        assert parent.snapshot_commit_sha == '63491908290e6874dbaaf2b15c2a96473aad1324'
        snapshot = db.get(CodeSnapshot, parent.snapshot_id)
        assert snapshot and snapshot.published and snapshot.repository_id == parent.repository_id
        assert snapshot.tenant_id == parent.tenant_id and snapshot.commit_sha == parent.snapshot_commit_sha
        outbox = db.get(InvestigationReportOutbox, task.id)
        assert outbox and outbox.status == 'processed' and outbox.tenant_id == parent.tenant_id
        reports = db.scalars(select(InvestigationReport).where(InvestigationReport.investigation_id == parent.id)).all()
        assert len(reports) == 1
        report = reports[0]
        assert report.report_job_id == task.id and report.snapshot_id == snapshot.id
        assert report.repository_id == parent.repository_id and report.tenant_id == parent.tenant_id
        assert report.commit_sha == snapshot.commit_sha and report.provider == 'mock' and report.model == 'deterministic-v1'
        evidence = evidence_inputs(db, parent, snapshot)
        assert len(evidence) == 20
        rendered = render_report_payload(report.payload, parent=parent, evidence=evidence)
        references = [item for hypothesis in rendered['hypotheses']
                      for item in hypothesis['evidence'] + hypothesis['contradictory_evidence']]
        assert references
        allowed = {item['chunk_id']: item for item in evidence}
        for ref in references:
            item = allowed.get(ref['chunk_id'])
            assert item and ref['snapshot_id'] == snapshot.id and ref['commit_sha'] == snapshot.commit_sha
            assert (ref['path'], ref['symbol'], ref['start_line'], ref['end_line'], ref['url']) == (
                item['path'], item['symbol'], item['start_line'], item['end_line'], item['citation'])
        print(json.dumps({'report_id': report.id, 'report_job_id': task.id, 'investigation_id': parent.id,
            'report_status': task.status, 'report_attempts': task.attempts, 'outbox_status': outbox.status,
            'dispatch_attempts': outbox.attempts, 'snapshot_id': snapshot.id, 'commit_sha': snapshot.commit_sha,
            'provider': report.provider, 'model': report.model, 'persisted_report_count': len(reports),
            'parent_status': parent.status, 'parent_attempts': parent.attempts,
            'parent_evidence_count': len(evidence), 'valid_report_references': len(references)}))
except Exception:
    print('Report, parent or persisted evidence validation failed.', file=sys.stderr)
    raise SystemExit(1) from None
PY
# Print only allowlisted lifecycle fields from structured events for this exact task.
docker compose logs --no-color dispatcher worker | "$repo_root/.venv/bin/python" -c '
import json, sys
job = sys.argv[1]
allowed = {"report_job_claimed", "report_job_completed", "report_job_dispatched", "report_task_received", "report_task_finished"}
fields = {"event", "job_id", "task_id", "repository_id", "level"}
for line in sys.stdin:
    try:
        data = json.loads(line[line.index("{"):])
    except (ValueError, TypeError):
        continue
    if data.get("event") in allowed and data.get("job_id") == job:
        print(json.dumps({key: value for key, value in data.items() if key in fields}))
' "$report_job"
