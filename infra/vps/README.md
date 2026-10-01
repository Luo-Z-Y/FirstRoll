# FirstRoll single-server stack

These files run the hosted public beta on one rented Linux server:

| File | Purpose |
|---|---|
| `bootstrap.sh` | One-time root preparation of a fresh Ubuntu 24.04 server |
| `docker-compose.yml` | Caddy (TLS, static site, reverse proxy) plus the FirstRoll API container |
| `Caddyfile` | Hostnames, cache headers and the API proxy |
| `.env.example` | Template for `/opt/firstroll/.env`; the real file is never committed |
| `deploy.sh` | Release, rollback and status commands executed on the server |

The GitHub `VPS Release` workflow uploads `deploy.sh`, `docker-compose.yml` and `Caddyfile` from
the approved commit on every release, so the server always runs the reviewed versions.

Server preparation, DNS, the release contract, rollback and day-to-day operation are in
[docs/OPERATIONS.md](../../docs/OPERATIONS.md).
