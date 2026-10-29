# 0w_sv

[![tests](https://github.com/raizestudio/zerow_sv/actions/workflows/tests.yml/badge.svg)](https://github.com/raizestudio/zerow_sv/actions/workflows/tests.yml)

A small FastAPI service that provides utility APIs for links, secrets, webhooks, DNS, and HTTP diagnostics. It runs with PostgreSQL, Valkey, and RabbitMQ; background workers and a scheduler handle asynchronous work and periodic cleanup.

## Features

- **URL shortener** — create short codes with optional custom names, expiry, and burn-after-reading behavior.
- **Secret sharing** — store a supplied ciphertext and IV with a time-to-live and view limit. The API stores the supplied ciphertext; encryption and key management are not performed by these endpoints.
- **Webhook catcher** — create temporary capture sessions, inspect received requests, and receive live updates over WebSockets.
- **URL tracer** — follow redirects and report redirect details, tracking parameters, and a defanged URL.
- **DNS auditor** — inspect common DNS records and report DNSSEC, SPF, DMARC, and CAA findings.
- **HTTP runner** — make a bounded HTTP request and inspect its response and timing information.
- **Network probe** — check TCP port status for a target host.
- **Scheduled cleanup** — periodically purge expired links, secrets, and webhook sessions.

## Requirements

- Docker and Docker Compose (recommended), or Python 3.13+ and [`uv`](https://docs.astral.sh/uv/).
- For a local Python run: PostgreSQL, Valkey, and RabbitMQ must be available.

## Run with Docker Compose

From the repository root:

```sh
docker compose -f docker/docker-compose.yml up --build
```

Compose starts the API, worker, scheduler, PostgreSQL, Valkey, and RabbitMQ. By default, the API is available at <http://localhost:8002> and its interactive API reference is at <http://localhost:8002/docs>. ReDoc is available at <http://localhost:8002/redoc>.

Stop the services with:

```sh
docker compose -f docker/docker-compose.yml down
```

The database, cache, and broker data are kept in named Docker volumes when the services are stopped. The default credentials and configuration are for local development; change them before using this setup in a shared or production environment.

### Compose ports

| Service | Host port by default | Override |
| --- | ---: | --- |
| API | 8002 | `HOST_PORT` |
| PostgreSQL | 5433 | `HOST_DB_PORT` |
| Valkey | 6380 | `HOST_CACHE_PORT` |
| RabbitMQ AMQP | 5673 | `HOST_RABBITMQ_PORT` |
| RabbitMQ management UI | 15673 | `HOST_RABBITMQ_MGMT_PORT` |

The database, Valkey, and RabbitMQ host ports are bound to loopback by the Compose file. The API is published on the host interfaces configured by Docker.

## Run locally with uv

Install dependencies and prepare a local environment file:

```sh
uv sync
cp .env.example .env
```

Edit `.env` for the addresses, ports, and credentials of your local PostgreSQL, Valkey, and RabbitMQ services. The application defaults to `localhost` for these services. When using the Compose dependencies from a host-run application, use the mapped host ports in the table above.

Start the API:

```sh
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API initializes its database connection and schemas on startup, and expects the configured cache and message broker to be reachable as well.

## Configuration

Settings are read from environment variables and `.env`. The names below correspond to the settings in `config.py` and describe the native `uv` setup. Compose supplies service hostnames and internal container ports, and currently defines development credentials directly in `docker/docker-compose.yml`; update the matching Compose service and application values together if you change them.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `0w_sv` | API title and Compose container-name prefix. |
| `HOST_PORT` | `8002` in Compose | Host port for the API. |
| `DB_HOST` | `localhost` | PostgreSQL hostname. |
| `DB_PORT` | `5432` | PostgreSQL port used by the application. |
| `DB_USER` | `jmpt` | PostgreSQL username. |
| `DB_PASSWORD` | `jmpt` | PostgreSQL password. |
| `DB_NAME` | `jmpt` | Application database name. |
| `DB_TEST_NAME` | `jmpt_test` | Database name used by the test fixture. |
| `CACHE_HOST` | `localhost` | Valkey hostname. |
| `CACHE_PORT` | `6379` | Valkey port used by the application. |
| `CACHE_DB` | `0` | Valkey database index. |
| `CACHE_DEFAULT_TTL` | `300` | Default cache TTL, in seconds. |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ hostname. |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port used by the application. |
| `RABBITMQ_USER` | `admin` | RabbitMQ username. |
| `RABBITMQ_PASSWORD` | `admin` | RabbitMQ password. |
| `HOST_DB_PORT` | `5433` in Compose | Host port mapped to PostgreSQL. |
| `HOST_CACHE_PORT` | `6380` in Compose | Host port mapped to Valkey. |
| `HOST_RABBITMQ_PORT` | `5673` in Compose | Host port mapped to RabbitMQ AMQP. |
| `HOST_RABBITMQ_MGMT_PORT` | `15673` in Compose | Host port mapped to RabbitMQ management UI. |

The `HOST_*` variables control host-side Compose port mappings; `DB_PORT`, `CACHE_PORT`, and `RABBITMQ_PORT` are the ports the application uses to connect to its dependencies.

## API overview

The full request and response schemas are available through the generated OpenAPI docs at `/docs` and `/openapi.json`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service name and basic status. |
| `GET` | `/health` | Health response and application version. |
| `POST` | `/url-shtnr/shorten` | Create a short link. |
| `GET` | `/url-shtnr/{short_code}` | Look up a short code and return its destination. This endpoint returns JSON; it does not issue an HTTP redirect. |
| `POST` | `/secrets` | Create a time- and view-limited secret record. |
| `GET` | `/secrets/{secret_id}` | Read secret metadata without consuming a view. |
| `POST` | `/secrets/{secret_id}/reveal` | Reveal the stored ciphertext and consume a view. |
| `POST` | `/webhooks/sessions` | Create a webhook capture session. |
| `GET` | `/webhooks/sessions/{session_id}/requests` | List captured requests for a session. |
| `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS` | `/webhooks/catch/{session_id}` | Capture an incoming webhook request. |
| WebSocket | `/webhooks/ws/{session_id}` | Receive live capture updates. |
| `POST` | `/url-trace` | Trace a URL's redirect chain. |
| `POST` | `/dns-audit` | Audit DNS records and related domain settings. |
| `POST` | `/http-runner` | Make an HTTP request and return response details. |
| `POST` | `/probe` | Check selected TCP ports on a target host. |

### Example: create a short link

```sh
curl -X POST http://localhost:8002/url-shtnr/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.org/article","expires_in":"7d"}'
```

The response contains a `short_code`. Look it up with `GET /url-shtnr/{short_code}`.

## Development and tests

Run the test suite with:

```sh
uv run pytest -v
```

Tests require PostgreSQL access and use `DB_TEST_NAME`. **The test setup drops and recreates that database**, so set it to a disposable test database and never point it at data you need to keep.

The repository's CI workflow also runs Ruff checks and the test suite.

## Security and deployment notes

- These routes do not implement user authentication. Put the service behind an appropriate authentication and access-control layer before exposing it beyond a trusted environment.
- The URL tracer, HTTP runner, DNS auditor, and network probe make outbound network requests. The request handlers include checks against private or otherwise restricted destinations, but those checks are not a substitute for deployment-level egress controls. Use these tools only on systems and domains you own or are authorized to assess.
- Webhook captures can contain request headers, query parameters, bodies, and client IP addresses. Treat captured data as sensitive.
- Replace development credentials, configure HTTPS at the deployment boundary, and avoid committing `.env` files or secrets.
