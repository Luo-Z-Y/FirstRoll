# Release Guide (V2)

This project has shifted to a V2 web + backend architecture.

## Scope

Release artifacts focus on:

1. Backend API (`app/backend`)
2. Web client (`app/web`)
3. Algorithm integration under `app/backend/algorithms`

Legacy Windows desktop packaging flow has been removed from the active release process.

## 1. Pre-release Checks

```bash
python -m compileall app/backend
node --check app/web/app.js
```

## 2. Version Update

1. Update `version` in `pyproject.toml`.
2. Refresh lockfile if dependencies changed:

```bash
uv lock
```

## 3. Validate API Contract

Run locally:

```bash
uv run firstroll
```

Then verify:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/contract
```

## 4. Validate Web Client

The backend serves the web client. Open `http://127.0.0.1:8000` and run one full
discovery and analysis pass:

1. Search for a film and confirm the Wikidata source label.
2. Import video.
3. Run analysis.
4. Confirm all tabs render.
5. Export JSON + CSV outputs.

## 5. Tag and Publish

1. Create annotated tag (for example `v0.2.0`).
2. Push branch and tag.
3. Publish release notes including API contract changes.
