# Fëanor Tutorial

This guide walks through the core workflows using the local MVP stack.
By the end you will have registered a dataset, run a federated query, submitted a workflow execution, and streamed its logs.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker | 24+ (with Compose plugin) | https://docs.docker.com/get-docker/ |
| pixi | any | `curl -fsSL https://pixi.sh/install.sh \| bash` |
| git | any | system package manager |

Clone the repo and run the installer once:

```bash
git clone <repo-url> feanor
cd feanor
./install.sh
```

`install.sh` will:
1. Copy `.env.example` → `.env` and generate the Airflow Fernet key
2. Build the `api` and `airflow` Docker images
3. Start all services with `docker compose --project-name feanor up -d`
4. Wait for every service to report healthy
5. Run `pixi install` to install the `feanor` CLI

All subsequent CLI examples use `pixi run feanor`. If you have activated the pixi shell (`pixi shell`) you can omit `pixi run`.

## Service URLs

| Service | URL | Default credentials |
|---|---|---|
| API | http://localhost:8000 | — |
| API docs (Swagger) | http://localhost:8000/docs | — |
| Keycloak | http://localhost:8080 | admin / changeme |
| MinIO console | http://localhost:9001 | minioadmin / changeme |
| Trino | http://localhost:18080 | — |
| Airflow | http://localhost:8090 | admin / admin |
| Traefik dashboard | http://localhost:8081 | — |

---

## 1. Authentication

Fëanor uses Keycloak for identity. The CLI authenticates via the OAuth2 device flow — it prints a URL, you open it in a browser, and the token is cached in `~/.feanor/config.yaml`.

```bash
pixi run feanor auth login
```

Confirm who you are:

```bash
pixi run feanor auth whoami
```

```
Profile : local
API URL : http://localhost:8000
Keycloak: http://localhost:8080
Realm   : feanor
```

For CI or scripts, export a bearer token or service-account credentials instead of using the device flow:

```bash
export FEANOR_TOKEN="<your-bearer-token>"
# or
export FEANOR_CLIENT_ID="my-sa"
export FEANOR_CLIENT_SECRET="secret"
```

---

## 2. System health

```bash
pixi run feanor system health
```

All services should show `healthy`. If any service is still starting, wait a minute and retry.

---

## 3. Datasets

A dataset is a registered pointer to data — it stores metadata and the source reference, not the data itself.

### Register a dataset

Register a CSV file in MinIO (uploaded there separately, or pointing at any supported source):

```bash
pixi run feanor datasets register \
    --name "orders-2024" \
    --source "s3://feanor-test/orders/2024/orders.csv"
```

You can also register a Postgres table:

```bash
pixi run feanor datasets register \
    --name "customers" \
    --source "pg://feanor/public/customers"
```

The `--source` field accepts any URI that maps to a configured connector. The control plane stores the reference — it does not copy the data.

### List and inspect

```bash
pixi run feanor datasets list
pixi run feanor datasets get <dataset-id>
```

Pass `--output json` or `--output yaml` to any command for machine-readable output:

```bash
pixi run feanor datasets list --output json | jq '.[0].id'
```

### Delete

```bash
pixi run feanor datasets delete <dataset-id>
```

---

## 4. Federated SQL queries

Fëanor routes `feanor query` through Trino, which can join data across catalogs (Postgres, MinIO/Hive, HTTP) in a single query.

### List available catalogs

```bash
pixi run feanor query "SHOW CATALOGS"
```

Expected output in the local MVP:

```
 Catalog
─────────
 hive
 pg
 system
 tpch
```

### Query the built-in sample data

Trino ships a `tpch` catalog for testing. Use it to verify the stack before loading your own data:

```bash
pixi run feanor query "SELECT orderkey, orderstatus, totalprice \
    FROM tpch.sf1.orders LIMIT 5"
```

### Query Postgres

The `pg` catalog mirrors the control plane database. If you have registered connectors or datasets, their metadata lives here:

```bash
pixi run feanor query "SELECT id, name, source_ref FROM pg.feanor.datasets LIMIT 10"
```

### Cross-catalog join

```sql
pixi run feanor query "
  SELECT o.orderkey, c.name
  FROM tpch.sf1.orders o
  JOIN pg.feanor.datasets d ON d.name = 'orders-2024'
  LIMIT 5
"
```

### Output formats

```bash
# Default: rich table in terminal
pixi run feanor query "SELECT 1 AS n"

# JSON — pipe to jq
pixi run feanor query --output json "SELECT 1 AS n"

# Limit rows
pixi run feanor query --max-rows 100 "SELECT * FROM tpch.sf1.lineitem"
```

---

## 5. Execution templates

Templates define the infrastructure tier an algorithm runs on. The three built-in tiers are:

| Template | Use case |
|---|---|
| `serverless_standard` | Short-lived, event-driven jobs |
| `container_job_standard` | Isolated, medium-duration containers |
| `distributed_spark_medium` | Large-scale parallel Spark jobs |

List registered templates:

```bash
pixi run feanor templates list
```

---

## 6. Workflows

A workflow (algorithm) declares what code to run and which execution template to use.

### Create a workflow

```bash
pixi run feanor workflows create \
    --name "hello-world" \
    --slug "hello-world" \
    --version "v1" \
    --execution-template "container_job_standard" \
    --image "python:3.11-slim" \
    --command "python -c 'print(\"hello from feanor\")'"
```

### List workflows

```bash
pixi run feanor workflows list
pixi run feanor workflows list --slug hello-world
```

### Inspect a specific version

```bash
pixi run feanor workflows get <workflow-id>
```

---

## 7. Executions

An execution is a single run of a workflow. The control plane dispatches it to the appropriate compute tier — you never pick the infrastructure directly.

### Submit (fire and forget)

```bash
pixi run feanor workflows run hello-world:v1
```

This returns immediately with the execution ID and status `pending`.

### Submit with inputs

```bash
pixi run feanor workflows run hello-world:v1 \
    --input dataset_id=<dataset-id> \
    --input threshold=0.95
```

### Submit and wait for completion

```bash
pixi run feanor workflows run hello-world:v1 --wait --timeout 120
```

The CLI uses long-polling — it does not spin; it blocks until the execution reaches a terminal state or the timeout fires.

### List and inspect

```bash
pixi run feanor executions list
pixi run feanor executions list --status running
pixi run feanor executions list --workflow-id <workflow-id>

pixi run feanor executions get <execution-id>
```

### Cancel a running execution

```bash
pixi run feanor executions cancel <execution-id>
```

---

## 8. Logs

### Print logs once

```bash
pixi run feanor executions logs <execution-id>
```

### Print the last N lines

```bash
pixi run feanor executions logs <execution-id> --tail 50
```

### Stream logs until the execution finishes

```bash
pixi run feanor executions logs <execution-id> --follow
```

`--follow` polls the log store (MinIO) and exits with code 0 on success or 1 on failure, making it suitable for CI scripts.

---

## 9. SDK usage

Import `feanor.Client` for synchronous use or `feanor.AsyncClient` for async code.

### Sync client

```python
from feanor import Client

client = Client()  # reads FEANOR_TOKEN or cached token from ~/.feanor/config.yaml

# Register a dataset
ds = client.datasets.register(
    name="sales-q3",
    source="s3://feanor-test/sales/q3/",
)
print(ds.id, ds.name)

# Run a query
result = client.query("SELECT COUNT(*) AS n FROM tpch.sf1.orders")
print(result.rows)  # [{'n': 1500000}]

# Submit a workflow and wait
run = client.executions.submit(
    workflow="hello-world:v1",
    inputs={"dataset_id": ds.id},
    wait=True,
    timeout=120,
)
print(run.status)  # 'succeeded'
```

### Async client

```python
import asyncio
from feanor import AsyncClient

async def main():
    async with AsyncClient() as client:
        datasets = await client.datasets.list()
        for ds in datasets:
            print(ds.name, ds.source_ref)

        result = await client.query("SELECT 1 AS ping")
        print(result.rows)

asyncio.run(main())
```

### Service-account client (CI / automation)

```python
import os
from feanor import Client

client = Client()
# Set FEANOR_CLIENT_ID and FEANOR_CLIENT_SECRET in the environment;
# the SDK picks them up and uses the client-credentials grant automatically.
```

---

## 10. Named profiles

Multiple profiles let you point at different environments (local, staging, production) without changing environment variables.

`~/.feanor/config.yaml`:

```yaml
default_profile: local

profiles:
  local:
    api_url: http://localhost:8000
    keycloak_url: http://localhost:8080
    realm: feanor

  staging:
    api_url: https://api.staging.feanor.example.com
    keycloak_url: https://auth.staging.feanor.example.com
    realm: feanor
```

Switch profiles with `--profile` or `FEANOR_PROFILE`:

```bash
pixi run feanor --profile staging system health
FEANOR_PROFILE=staging pixi run feanor datasets list
```

---

## 11. Common environment variables

| Variable | Purpose |
|---|---|
| `FEANOR_API_URL` | Override the API base URL |
| `FEANOR_TOKEN` | Provide a bearer token directly |
| `FEANOR_CLIENT_ID` | Service account client ID |
| `FEANOR_CLIENT_SECRET` | Service account client secret |
| `FEANOR_PROFILE` | Select a named config profile |

---

## 12. Stack management

```bash
# Stop without removing volumes
docker compose --project-name feanor stop

# Start again
docker compose --project-name feanor start

# Tail all service logs
docker compose --project-name feanor logs -f

# Tail a specific service
docker compose --project-name feanor logs -f api

# Destroy everything (including volumes — data is gone)
docker compose --project-name feanor down -v
```

Run database migrations after pulling new code:

```bash
pixi run db-upgrade
```

---

## Troubleshooting

**`feanor auth login` hangs or fails**
Keycloak takes up to 3 minutes to start. Check: `docker compose --project-name feanor logs keycloak | tail -20`. Wait for `Started in ... ms`.

**`feanor query` returns "No catalogs"**
Trino is still initializing. Run `curl -s http://localhost:18080/v1/info | jq .starting` — it should return `false` when ready.

**API returns 401 Unauthorized**
Your cached token has expired. Run `pixi run feanor auth login` to refresh it.

**Airflow DAGs not visible**
DAG files live in `dags/`. Any `.py` file placed there is picked up automatically within 30 seconds.

**Port conflict on startup**
Check which ports are in use (`ss -tlnp | grep -E '5432|8080|8090|9000|9001|18080'`) and stop the conflicting process before running `install.sh`.
