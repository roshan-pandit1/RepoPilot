# Local operations and recovery

For the existing `repopilot-local` environment, use the targeted
[final-demo execution plan](final-demo-execution-plan.md). A private application backup and
isolated restore comparison were completed under Stage 1 authorization; see
[verification](verification.md) for the actual artifacts and limits. The generic `docker compose` examples below are historical;
they do not select `repopilot-local` and must not be used for this database.

RepoPilot's Compose configuration keeps web and API on loopback and PostgreSQL and Redis on
the internal network. The API, dispatcher and workers use the same application modules.
Compose waits for PostgreSQL, Redis and the migration service before starting application
processes. The web container waits for API readiness. `/health` reports process liveness;
`/ready` checks selected database tables and Redis, but **does not verify the Alembic revision,
worker health, GitHub reachability or successful job processing**.

## Configuration and migration

Use [the example](../.env.example) or generate a private local `.env` with
`python3 infra/init_env.py`; the helper refuses overwrites. Generated demo settings are for a
private development environment, never public or production. Real GitHub sign-in needs the
fixed callback, client settings and encryption key described in the README. The mock report
provider defaults to `mock` and requires no OpenAI key. Redis and database credentials,
GitHub secrets, session cookies, issue content and backups must be kept private. Reverse proxies
must not log OAuth callback query strings; the API Docker command disables access logging.

`make dev` runs `alembic upgrade head` against the configured Compose database before starting
services. For an existing application database, do not run it or `make migrate` until the
operator has separately authorized a migration, checked the target and current revision,
reviewed the migration chain, made a protected backup and planned an isolated restore. Never
use the development demo publicly. A migration test on a disposable database is not permission
to migrate the normal application database.

## Backups and restore

No automatic backup schedule, retention policy or offsite recovery is implemented. An earlier
application archive was not independently restored; the later Stage 1 backup was restored into
an isolated database with the limits recorded in [verification](verification.md).
With separate operator authorization, the targeted plan uses a custom-format backup in a
private, unique directory and does not place database passwords in command arguments.

Archive-list success only shows that PostgreSQL can read its catalog; it is not a restore.
Store authorized application backups encrypted with restricted access and an appropriate
retention policy. Before migration or release, an operator should restore into a **new, empty,
isolated** PostgreSQL/pgvector instance with matching major version, never into the normal
database; inspect archive provenance, extension availability, migration version, key table
counts and representative application reads, and record failures. Do not use `--clean` against
an existing database. Database dumps can contain private issue text and token ciphertext.

For a separately authorized restore drill, the following targets only a newly created,
network-isolated container and its empty `restore_fixture` database. Set `backup_dir` to the
private directory containing the reviewed archive. The container uses local trust authentication
only inside its isolated namespace and is retained for inspection:

```sh
restore_run="$(openssl rand -hex 8)"
restore_container="repopilot-restore-${restore_run}"
docker run --pull=never -d --name "$restore_container" --label repopilot-purpose=restore-drill \
  --network none -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=restore_fixture \
  -e POSTGRES_DB=restore_fixture pgvector/pgvector:pg16
docker exec "$restore_container" pg_isready -U restore_fixture -d restore_fixture
docker exec -i "$restore_container" pg_restore --exit-on-error --no-owner --no-privileges \
  -U restore_fixture -d restore_fixture < "$backup_dir/database.dump"
```

If `pg_isready` reports startup is incomplete, wait and run it again before `pg_restore`.
Review the restore output and validate the restored schema and application data with the
operator; a zero exit alone is not an application-level recovery test.

The finalization pass separately tested `pg_dump -Fc` and `pg_restore --exit-on-error` in a new
network-isolated PostgreSQL 16/pgvector container with two synthetic rows. Row count and vector
values matched after restore. This demonstrates the tool path only; it is not proof that an
application backup is complete or recoverable. The synthetic container and volume were retained.
