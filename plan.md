# Fëanor — Architecture plan

## What this document is

This is the canonical reference for Fëanor, the federated data and compute
platform. It describes the architecture, the rationale behind key decisions, the
phased build plan, and the contracts between layers. Agents and engineers should
treat this as the source of truth for structural decisions. Implementation details
(exact package versions, module internals) may evolve; the layer boundaries and
data flow described here should not change without a deliberate decision.

---

## Guiding principles

**API-first.** Every capability — data access, workflow submission, execution,
metadata management — is exposed through the REST API. The future UI and any
internal tooling are consumers of the same API as external users.

**Federated by default.** Data is accessed where it lives. Nothing is centralised
before it needs to be. Trino and DuckDB enable query-in-place across heterogeneous
sources.

**Template-driven execution.** Algorithms declare what kind of compute they need
(serverless / container / distributed). Fëanor provides it. Engineers do not
provision custom infrastructure per algorithm.

**Self-serve for scientists, power access for engineers.** The `feanor` SDK and CLI
must make the common path (register data, run a workflow, get results) trivially
easy. The escape hatch (custom Terraform, raw API, DuckDB) must be fully accessible
for those who need it.

**Hybrid from day one.** Local MVP and cloud production share the same codebase,
the same API contracts, and the same Terraform module library. The only difference
is the values passed to environment variables.

---

## System layers

```
┌─────────────────────────────────────────────────────────────┐
│     Clients: feanor CLI · feanor SDK · (future UI)          │
├─────────────────────────────────────────────────────────────┤
│           Keycloak IAM — realm: feanor  (OIDC / OAuth2)     │
├─────────────────────────────────────────────────────────────┤
│              API gateway  (Traefik → API GW)                 │
├──────────────────┬──────────────────┬───────────────────────┤
│  Control plane   │  Template        │  Postgres              │
│  (FastAPI)       │  registry        │  (metadata store)      │
├──────────────────┴──────────────────┴───────────────────────┤
│           Orchestration: Airflow · Trino · DuckDB            │
├──────────────────────────────────────────────────────────────┤
│    Execution:  Serverless │ Container jobs │ Distributed     │
├──────────────────────────────────────────────────────────────┤
│    Federated data:  SQL · Object stores · Files · HTTP       │
├──────────────────────────────────────────────────────────────┤
│      Infrastructure: Terraform modules + escape hatch        │
└──────────────────────────────────────────────────────────────┘
```

---

## Layer-by-layer design

### Layer 1 — Identity and access (Keycloak)

Keycloak is the single identity provider. No service implements its own auth.
Realm name: `feanor`.

**Roles:**

| Role | Who | Can do |
|---|---|---|
| `platform_admin` | Platform team | Everything, including infrastructure escape hatch |
| `engineer` | Data engineers | Create/manage workflows, templates, connectors |
| `analyst` | Scientists / analysts | Register datasets, submit executions, query data |
| `service_account` | Airflow, internal services | Submit executions, read metadata |

**Grant types by client:**

- `feanor` CLI: device authorization flow (browser-based login from terminal)
- `feanor` SDK (interactive): authorization code + PKCE
- `feanor` SDK (service account / CI): client credentials
- Airflow and internal services: client credentials

Token lifetimes: access tokens 15 minutes, refresh tokens 8 hours. The `feanor`
SDK token manager handles refresh transparently.

---

### Layer 2 — API gateway

Single ingress. Validates the JWT on every request before forwarding to the control
plane. Does not contain business logic.

**Responsibilities:**
- JWT signature verification (Keycloak public key via JWKS endpoint)
- Rate limiting (per-user and per-IP)
- Request routing to control plane services
- TLS termination
- Access logging

**Local MVP:** Traefik v3 configured via labels on Docker Compose services.
**Cloud:** AWS API Gateway (HTTP API mode) or GCP API Gateway.

The OpenAPI spec published at `/openapi.json` is generated from the FastAPI app and
represents the authoritative contract. The `feanor` SDK is validated against this spec.

---

### Layer 3 — Control plane

The brain of Fëanor. A FastAPI application backed by PostgreSQL.

**Database schema (high-level):**

| Table | Key columns |
|---|---|
| `datasets` | id, name, source_ref, schema_hints, created_by, lineage_refs |
| `workflows` | id, slug, version, definition, execution_template_id |
| `executions` | id, workflow_id, status, inputs, result_ref, log_ref, started_at, ended_at |
| `execution_templates` | id, name, type (serverless/container/distributed), config |
| `connectors` | id, name, type, config (encrypted), owner |
| `system_state` | key, value (key-value for health and config flags) |

**API surface (all under `/v1/`):**

```
GET/POST         /datasets
GET/PATCH/DELETE /datasets/{id}

GET/POST         /workflows
GET/PATCH/DELETE /workflows/{id}
POST             /workflows/{id}/run        → creates an execution

GET              /executions
GET              /executions/{id}
GET              /executions/{id}/logs
POST             /executions/{id}/cancel

GET/POST         /templates
GET              /templates/{id}

GET/POST         /connectors
GET/PATCH/DELETE /connectors/{id}

POST             /infrastructure/custom     → escape hatch (platform_admin only)
GET              /system/health
GET              /system/ready
```

All list endpoints: cursor-based pagination (`?cursor=&limit=`), filtering
(`?status=running`), sorting (`?sort=created_at&order=desc`).

**Execution dispatch flow:**

1. Client calls `POST /v1/workflows/{id}/run` with inputs.
2. Control plane creates an `execution` record with status `pending`.
3. Control plane looks up the workflow's `execution_template`.
4. Control plane dispatches to the appropriate execution backend:
   - `serverless` → invoke Lambda / Cloud Run function
   - `container_job` → submit Fargate / Cloud Run Job task
   - `distributed` → submit Spark / Ray job
5. Execution worker updates status via the control plane API as it runs.
6. On completion, worker writes `result_ref` (S3/GCS path) and `log_ref`.
7. Client polls `GET /v1/executions/{id}` or uses long-poll endpoint.

---

### Layer 4 — Orchestration and compute engines

**Airflow** owns scheduling. DAGs are Python files that call the control plane API
using the `feanor` SDK (service account credentials). Airflow does not directly
invoke compute and does not write to the control plane database.

A standard DAG pattern:

```python
from feanor import Client

client = Client()  # uses FEANOR_CLIENT_ID / FEANOR_CLIENT_SECRET from env

with DAG("daily-sales-etl", schedule="@daily") as dag:
    run = PythonOperator(
        task_id="run_etl",
        python_callable=lambda: client.executions.submit(
            workflow="sales-etl:v3",
            inputs={"date": "{{ ds }}"},
            wait=True,
        )
    )
```

**Trino** is the federated query layer. It runs as a coordinator + workers and holds
catalog configurations pointing at each registered data source. Scientists and
engineers query Trino directly via the SDK (`client.query(sql)`) or via the CLI
(`feanor query "SELECT ..."`). Trino is also used by Airflow DAGs for data
validation steps.

**DuckDB** runs in-process inside execution jobs. It is the engine of choice for:
- Reading Parquet/CSV files from object storage
- Local aggregations and transforms on fetched data
- Fast analytical queries that don't need to cross source boundaries

Do not deploy DuckDB as a server. It is always embedded in a Python process.

---

### Layer 5 — Execution layer

**Template types and their config:**

`serverless_standard`
- Max duration: 15 minutes
- Max memory: 3 GB
- Stateless — no persistent disk
- Input/output via object store (S3/MinIO)
- Use for: lightweight transforms, data validation, API calls

`container_job_standard`
- Max duration: 24 hours
- Configurable CPU and memory
- Ephemeral disk available
- Use for: ML training, medium ETL, anything needing a custom runtime

`container_job_gpu`
- Same as above plus GPU allocation
- Use for: model training, inference batch jobs

`distributed_spark_medium`
- Spark 3.x, auto-scaling cluster
- Use for: large-scale joins, aggregations over TB-scale data

**Execution worker contract:**

Every execution worker (regardless of type) must:
1. Accept inputs from the control plane as a JSON payload or object store reference.
2. Authenticate to the control plane API using a `service_account` token from Fëanor's
   Keycloak realm.
3. Update execution status at start (`running`), at intervals if long-running, and
   at completion (`succeeded` or `failed`).
4. Write results to the designated object store path (`result_ref`).
5. Write logs to the designated log sink (`log_ref`).
6. Never write directly to the control plane database.

---

### Layer 6 — Federated data access

The federated data access layer is not a separate service — it is the combination
of Trino catalogs, DuckDB connectors, and connector metadata registered in the
control plane.

**Connector registration flow:**

1. Admin calls `POST /v1/connectors` with type and config (credentials encrypted
   at rest using Fëanor's secrets manager).
2. Control plane stores the connector record.
3. Trino coordinator is updated with the new catalog config (hot-reload or restart,
   depending on the Trino version and connector type).
4. Connector is now queryable via Trino as `<connector_name>.<schema>.<table>`.

**Source type → Trino connector mapping:**

| Source type | Trino connector |
|---|---|
| PostgreSQL | `postgresql` |
| MySQL | `mysql` |
| S3 / MinIO | `hive` (with Hive metastore) or `delta` |
| HTTP / REST | `http` (custom or third-party) |
| Local files | `file` (dev/testing only) |

**Local MVP:** MinIO serves as the S3-compatible object store. All code referencing
S3 must use the AWS SDK with a configurable endpoint URL — never hardcode S3 hostnames.

---

### Layer 7 — Infrastructure

**Terraform module library structure:**

```
terraform/
  modules/
    execution-serverless/     # Lambda / Cloud Run function
    execution-container-job/  # Fargate / Cloud Run Job
    execution-distributed/    # Spark / Ray cluster
    control-plane/            # FastAPI service + RDS/Cloud SQL
    airflow/                  # MWAA / Composer
    trino/                    # Trino cluster on ECS/GKE
    keycloak/                 # Keycloak on EC2/GCE or managed
    networking/               # VPC, subnets, security groups
    object-store/             # S3 bucket / GCS bucket + policies
  environments/
    local/                    # Docker Compose (not Terraform)
    staging/
    prod/
```

Every module accepts `env`, `project` (default: `feanor`), and `region` as
required variables. No defaults for `env` or `region` — explicit is better
than implicit.

**Escape hatch process:**

1. Admin prepares a `.tf` file or zip of Terraform files.
2. Admin calls `POST /v1/infrastructure/custom` with the payload (or uses
   `feanor infrastructure apply --file custom.tf`).
3. Control plane validates the Terraform (lint + `plan`) in a sandboxed environment.
4. If plan is clean, admin approves and control plane runs `apply`.
5. Resource state is tracked in the control plane under the submitting admin's account.
6. Destruction is available via `DELETE /v1/infrastructure/custom/{id}`.

---

### Layer 8 — CLI and SDK (`feanor`)

**Package layout:**

```
feanor/
  __init__.py              # exports Client, AsyncClient
  client.py                # sync Client wrapping AsyncClient
  async_client.py          # AsyncClient (primary implementation)
  auth.py                  # TokenManager: acquire, cache, refresh
  config.py                # profile loading from ~/.feanor/config.yaml
  http.py                  # shared httpx client, retry logic
  models/                  # Pydantic v2 models mirroring API schemas
    dataset.py
    workflow.py
    execution.py
    template.py
  resources/               # resource namespaces
    datasets.py
    workflows.py
    executions.py
    templates.py
    system.py
  cli/
    __init__.py            # typer app, entry point: feanor
    commands/
      auth.py              # login, whoami, logout
      datasets.py
      workflows.py
      executions.py
      query.py
      templates.py
      system.py
      infrastructure.py
```

**Config file format (`~/.feanor/config.yaml`):**

```yaml
default_profile: local

profiles:
  local:
    api_url: http://localhost:8000
    keycloak_url: http://localhost:8080
    realm: feanor
  staging:
    api_url: https://api.staging.example.com
    keycloak_url: https://auth.staging.example.com
    realm: feanor
  prod:
    api_url: https://api.example.com
    keycloak_url: https://auth.example.com
    realm: feanor
```

---

## Build phases

### Phase 0 — Foundations (weeks 1–2)

Get the skeleton running locally end-to-end.

- [ ] Docker Compose stack: Postgres, MinIO, Keycloak (`feanor` realm), Traefik
- [ ] Keycloak realm configured: roles, dev users, service account for Airflow
- [ ] FastAPI app skeleton: health endpoints, envelope middleware, OpenAPI spec
- [ ] Alembic migrations for initial schema (datasets, workflows, executions, templates)
- [ ] Traefik routing to FastAPI with JWT validation
- [ ] `feanor` package skeleton: auth module + `Client` stub
- [ ] `~/.feanor/config.yaml` loading and `--profile` flag

**Done when:** `feanor login && feanor system health` returns green against
the local stack.

---

### Phase 1 — Control plane CRUD (weeks 3–4)

Implement the full resource API.

- [ ] `POST/GET/PATCH/DELETE /v1/datasets`
- [ ] `POST/GET/PATCH/DELETE /v1/workflows`
- [ ] `GET /v1/executions`, `GET /v1/executions/{id}`
- [ ] `GET/POST /v1/templates` with seed data for the four standard templates
- [ ] `GET/POST /v1/connectors`
- [ ] Role enforcement on all endpoints
- [ ] `feanor` SDK resource namespaces matching each endpoint
- [ ] `feanor` CLI commands for all resources
- [ ] Contract tests for all endpoints

**Done when:** a scientist can run `feanor datasets register` and `feanor workflows list`
against the local stack and see correct results.

---

### Phase 2 — Execution dispatch (weeks 5–6)

Wire up actual job execution.

- [ ] `POST /v1/workflows/{id}/run` → creates execution record + dispatches
- [ ] Serverless worker template (Docker-based locally, Lambda-compatible)
- [ ] Worker contract: status updates, result writing, log writing
- [ ] `GET /v1/executions/{id}/logs` endpoint
- [ ] Long-poll endpoint for `executions.submit(wait=True)`
- [ ] `POST /v1/executions/{id}/cancel`
- [ ] SDK: `client.executions.submit(wait=True)` with long-polling
- [ ] CLI: `feanor executions logs <id> --follow`

**Done when:** a scientist can run `feanor workflows run <id>` and stream logs
in real time, then retrieve a result reference.

---

### Phase 3 — Federated data access (weeks 7–8)

Connect Trino and DuckDB to real data sources.

- [ ] Trino in Docker Compose with PostgreSQL and MinIO/S3 catalogs
- [ ] Connector registration API wired to Trino catalog config
- [ ] `client.query(sql)` SDK method (Trino over HTTP)
- [ ] `feanor query "SELECT ..."` CLI command with `--output` formats
- [ ] DuckDB wrapper utility for use inside execution workers
- [ ] End-to-end test: register S3 connector → query via Trino → write result

**Done when:** `feanor query "SELECT * FROM minio.default.my_table LIMIT 10"`
returns data without moving it.

---

### Phase 4 — Airflow orchestration (weeks 9–10)

Integrate Airflow as a DAG-driven orchestrator.

- [ ] Airflow in Docker Compose with LocalExecutor
- [ ] Airflow service account in Keycloak (`feanor` realm, `service_account` role)
- [ ] `feanor` SDK installed in Airflow image, credentials injected via env
- [ ] Example DAG: scheduled workflow submission via `feanor` SDK
- [ ] Airflow DAG for data validation (Trino query → assertion → pass/fail)
- [ ] Airflow connection pool for control plane API calls

**Done when:** a DAG runs on schedule, submits a workflow via the SDK, and the
execution record in the control plane reflects the result.

---

### Phase 5 — Cloud lift (weeks 11–14)

Promote the local stack to cloud.

- [ ] Terraform modules for all services (execution tiers, control plane, Airflow, Trino)
- [ ] Staging environment deployed end-to-end via Terraform (`project = feanor`)
- [ ] CI/CD pipeline: lint → test → build images → push → terraform apply (staging)
- [ ] Secrets managed via AWS Secrets Manager or GCP Secret Manager
- [ ] Trino on ECS or GKE with S3/RDS catalogs
- [ ] Lambda / Cloud Run execution worker for `serverless_standard` template
- [ ] Fargate / Cloud Run Jobs for `container_job_standard` template
- [ ] Production environment checklist: TLS, auth hardening, rate limits, alerting

**Done when:** the full Phase 1–4 test suite passes against the staging cloud environment.

---

### Phase 6 — Hardening and escape hatch (weeks 15–16)

Fill gaps before opening to the full user base.

- [ ] Escape hatch API (`/v1/infrastructure/custom`) with Terraform plan/apply sandbox
- [ ] `feanor infrastructure apply --file custom.tf` CLI command
- [ ] Distributed execution template (`distributed_spark_medium`) on EMR Serverless or Dataproc
- [ ] Lineage tracking: `datasets.lineage_refs` populated by execution workers
- [ ] Admin CLI commands: user management, connector audit, execution purge
- [ ] Load testing: 50 concurrent workflow submissions
- [ ] Security review: JWT claims, role enforcement audit, connector credential encryption

**Done when:** Fëanor is ready for onboarding the first wave of users.

---

## Key design decisions and rationale

**Airflow calls the API, not the database.** This keeps Airflow replaceable. If we
later swap Airflow for Prefect or Dagster, the DAGs change but the control plane
does not. It also means all execution state flows through a single auditable path.

**Trino and DuckDB are not redundant.** Trino spans sources across the network.
DuckDB runs inside a job process on already-fetched or locally-accessible data.
They solve different problems. Trino is always-on infrastructure; DuckDB is a
library imported by worker code.

**Serverless-first, not serverless-only.** Fëanor defaults to serverless execution
templates because they eliminate idle infrastructure costs and cold-start provisioning.
Container jobs and distributed compute are available for workloads that genuinely
need them — not as defaults.

**One Python package for CLI and SDK.** The `feanor` CLI imports from the `feanor`
SDK. Any improvement to the SDK (better error messages, retry logic, a new resource
method) is immediately available in the CLI. There is one HTTP client and one auth
module to maintain.

**Escape hatch as a first-class API resource.** Custom Terraform in Fëanor is not
a workaround — it is a documented, audited, role-gated path. This makes it safe to
offer without making it tempting to overuse.

**Everything is namespaced to `feanor`.** Keycloak realm, Docker Compose project,
Terraform tag, config directory, CLI binary, Python package — all `feanor`. This
makes the system easy to reason about, easy to search in logs, and avoids collisions
in shared environments.

---

## Out of scope (current phase)

- UI / catalog layer
- Kafka / Kinesis stream ingestion
- Multi-cloud Terraform (single cloud target per deployment)
- Billing, metering, or chargeback
- Data quality / Great Expectations integration (future)
- ML model registry (future)
