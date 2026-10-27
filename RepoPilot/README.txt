RepoPilot Implementation Blueprint — October 26, 2026

Files:
- BLUEPRINT.md: complete 24-week product/architecture/AI/retrieval/security/cost/deployment/placement plan
- schema.sql: 22-table PostgreSQL/pgvector reference schema, with tenant RLS examples
- openapi.yaml: 17-path OpenAPI 3.1 reference contract

These files are architecture/reference artifacts, not a drop-in runnable service.
Review permissions and security settings, implement migrations, validate against
current provider docs, and test before deploying to production.

Suggested starting order:
1. Read sections 1–4 and 16 of BLUEPRINT.md.
2. Scaffold monorepo using section 9.
3. Translate schema.sql into Alembic migrations.
4. Implement API / webhook contracts in openapi.yaml.
5. Make the first week testable before adding any LLM.
