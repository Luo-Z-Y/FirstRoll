# FirstRoll single-server stack

These files run the public beta on one rented Linux server instead of Azure:

| File | Purpose |
|---|---|
| `bootstrap.sh` | One-time root preparation of a fresh Ubuntu 24.04 server |
| `docker-compose.yml` | Caddy (TLS, static site, reverse proxy) plus the FirstRoll API container |
| `Caddyfile` | Hostnames, cache headers and the API proxy |
| `.env.example` | Template for `/opt/firstroll/.env`; the real file is never committed |
| `deploy.sh` | Release, rollback and status commands executed on the server |

The GitHub `VPS Release` workflow uploads `deploy.sh`, `docker-compose.yml` and `Caddyfile` from
the approved commit on every release, so the server always runs the reviewed versions.

Purchase, DNS, bootstrap, first-release and operating instructions are in
[docs/HOSTING.md](../../docs/HOSTING.md); the release contract is in
[docs/RELEASE.md](../../docs/RELEASE.md).
