---
title: Alembic migrations — initial schema (datasets, workflows, executions, templates, connectors)
phase: 0
status: Completed
---

## Description

Define the SQLAlchemy 2.x ORM models and write the initial Alembic migration
that creates all Phase 0 tables. The schema must match the control plane data
model in the architecture plan exactly. No data seeding here except for the
four standard execution templates (seeded in a separate data migration).

## Acceptance criteria

- [ ] Alembic is initialised (`alembic/` directory with `env.py` and `alembic.ini`).
- [ ] SQLAlchemy 2.x declarative models exist under `api/app/models/`:
      - `Dataset` — `id (UUID PK)`, `name`, `source_ref`, `schema_hints (JSONB)`,
        `created_by`, `lineage_refs (JSONB)`, `created_at`, `updated_at`
      - `Workflow` — `id (UUID PK)`, `slug`, `version`, `definition (JSONB)`,
        `execution_template_id (FK)`, `created_at`, `updated_at`
      - `Execution` — `id (UUID PK)`, `workflow_id (FK)`, `status (enum)`,
        `inputs (JSONB)`, `result_ref`, `log_ref`, `started_at`, `ended_at`,
        `created_at`
      - `ExecutionTemplate` — `id (UUID PK)`, `name (unique)`, `type (enum)`,
        `config (JSONB)`, `created_at`
      - `Connector` — `id (UUID PK)`, `name`, `type`, `config_encrypted (BYTEA)`,
        `owner`, `created_at`, `updated_at`
      - `SystemState` — `key (PK, text)`, `value (JSONB)`, `updated_at`
- [ ] `Execution.status` enum values: `pending`, `running`, `succeeded`, `failed`,
      `cancelled`.
- [ ] `ExecutionTemplate.type` enum values: `serverless`, `container_job`, `distributed`.
- [ ] Initial Alembic migration runs cleanly against a fresh Postgres instance:
      `alembic upgrade head` succeeds with no errors.
- [ ] A second data migration seeds the four standard templates:
      `serverless_standard`, `container_job_standard`, `container_job_gpu`,
      `distributed_spark_medium`.
- [ ] `alembic downgrade -1` reverses both migrations cleanly.
- [ ] All timestamp columns default to `now()` at the DB level.

## Dependencies

- task-001 (Postgres must be running for migration testing)
- task-003 (FastAPI project structure must exist to house `api/app/models/`)

## Notes

- Use `UUID` primary keys throughout (Postgres native `uuid` type).
- `config_encrypted` on `Connector` is a placeholder (`BYTEA`); actual encryption
  logic is a Phase 6 concern. Store plaintext for MVP, document the gap.
- `JSONB` for all flexible/schemaless fields — not `JSON` or `TEXT`.
- All models should inherit from a `Base` declarative base and a `TimestampMixin`
  that provides `created_at` / `updated_at` automatically.
