# Run FirstRoll on Your Own Device

FirstRoll is a local-first web application. Each user runs one private copy of the
backend and frontend on their own computer, then opens it in an ordinary browser.
The key-free film catalogue works without a discovery credential. An optional TMDb Read Access
Token improves search speed, posters and crew coverage.

## What Runs Where

```text
Browser → http://127.0.0.1:8000 → FirstRoll FastAPI app
                                   ├── polished web interface
                                   ├── optional TMDb primary catalogue
                                   ├── key-free Wikidata/Wikipedia fallback
                                   └── local video-analysis pipeline
```

`127.0.0.1` means the service is reachable only from the computer running FirstRoll.
It is not exposed to the local network or public internet.

## Requirements

- macOS, Windows or Linux
- Git
- Python 3.11 or 3.12
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- FFmpeg for video analysis
- An internet connection for live catalogue search
- Sufficient disk space for Python computer-vision packages and bundled model files

The open catalogue remains available without TMDb; a small bundled catalogue covers a complete
network outage.

## 1. Install the System Tools

### macOS

With [Homebrew](https://brew.sh/) installed:

```bash
brew install git ffmpeg uv
```

### Windows

In PowerShell:

```powershell
winget install --id Git.Git -e
winget install --id Gyan.FFmpeg -e
winget install --id astral-sh.uv -e
```

Close and reopen PowerShell after installation so the new commands are available.

### Ubuntu or Debian Linux

```bash
sudo apt update
sudo apt install git ffmpeg curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal after installing `uv`.

## 2. Download FirstRoll

```bash
git clone https://github.com/Luo-Z-Y/FirstRoll.git
cd FirstRoll
```

## 3. Install FirstRoll

```bash
uv sync
```

`uv` creates a private Python environment inside the project and installs the locked
dependencies. The first installation can take a while because the film-analysis stack
includes large computer-vision packages.

## 4. Start the Local App

```bash
uv run firstroll
```

When the terminal reports that the server is running, open:

```text
http://127.0.0.1:8000
```

The discovery interface, Settings page and analysis API are all served by this one
process. Do not start a second frontend server.

## 5. Confirm It Works

1. Confirm that **Sign in** is visible in the header. Use `luo_zhiyang@outlook.com` and any password
   of at least eight characters. Reload the page and confirm that the local session persists.
2. Open **Settings → System settings** and confirm that the account displays an unlimited local
   FirstRoll allowance.
3. Search for a film using title, year and optionally director.
4. Confirm that discovery reports `TMDb · ready` when configured, or
   `TMDb · credentials required` followed by `Wikidata · ready` in key-free mode.
5. Open a film dossier and inspect its source link and evidence boundary.
6. Open **Analyse**, choose a short video clip and generate an analysis.

The health check is available at:

```text
http://127.0.0.1:8000/api/health
```

### Local test-account boundary

The local account works on any port only when both the browser URL and the connected HTTP client
are loopback (`localhost`, `127.0.0.1` or `::1`). It does not depend on a particular launcher or on
`FIRSTROLL_SERVE_HOSTED_FRONTEND`, so both `uv run firstroll` and
`./tools/preview_hosted_web.sh` expose the same test identity. Its browser token is rejected by every
non-loopback deployment. Local profile, preference and saved-film records are browser-specific test
data rather than Supabase rows; production accounts and cross-device persistence still use Supabase.
The loopback account also selects the hosted account shell, so the header contains **Discover**,
**Analyse** and **Settings** and Settings opens inside the application. This affects presentation
only: local clip analysis and other private-edition runtime capabilities remain available.
The unlimited label bypasses only FirstRoll's daily demo counters, not an external provider's
balance, rate limit or billing policy.

## Stop and Restart

Press `Ctrl+C` in the terminal to stop FirstRoll. Restart it later from the project
directory with:

```bash
uv run firstroll
```

## Update an Existing Installation

From the FirstRoll directory:

```bash
git pull
uv sync
uv run firstroll
```

## Optional Connectors

FirstRoll does not require TMDB or any other commercial film API. The Settings page at
`http://127.0.0.1:8000/settings` holds optional model and research connectors.

DeepSeek is the local LLM provider. Open Settings, enter the API key in
the DeepSeek card and choose **Save locally**. The key is stored write-only in
`.firstroll/settings.json`; FirstRoll returns only a masked status to the browser. As an
alternative, set `DEEPSEEK_API_KEY` before starting the backend. Open a film dossier and
choose **Generate study** to send that film's verified record, optional focus, attributed
critic claims and only the selected page-cited passages to DeepSeek. No full PDF,
embedding or local file path is transmitted. A deterministic quality gate checks the
draft; when it fails, FirstRoll permits one bounded repair call and labels any remaining
weakness as insufficient evidence.

The default model is `deepseek-v4-pro`, selected for more coherent long-form film-study
writing. Set `DEEPSEEK_MODEL=deepseek-v4-flash` before startup when lower latency and cost
matter more. Both models use the same structured evidence and quality controls.

### Optional Douban criticism adapter

Douban MCP is unofficial and may require a personal Douban cookie. Install it privately
inside FirstRoll's Git-ignored connector directory:

```bash
mkdir -p .firstroll/connectors
git clone https://github.com/moria97/douban-mcp.git .firstroll/connectors/douban-mcp
cd .firstroll/connectors/douban-mcp
npm install
cd ../../..
```

Open Settings, add the cookie only if anonymous access fails, and test the connector.
FirstRoll uses `search-movie` and `list-movie-reviews`, then asks DeepSeek to extract
attributed claims from the returned summaries. It stores the structured result privately
under `.firstroll/criticism`. Missing scenes, techniques, observations and timecodes
remain empty rather than being inferred.

Do not share a cookie or commit it to Git. Review summaries remain copyrighted secondary
sources; FirstRoll preserves a link to the original review and does not treat the review
as verified film observation.

See [DATA_SOURCES.md](DATA_SOURCES.md) for the current provider policy.

### Optional official Letterboxd API

FirstRoll can use API credentials granted by Letterboxd. Open Settings and enter both the
**Client ID** and **Client Secret**, then choose **Test connection**. Environment-managed
setups may instead define:

```bash
export LETTERBOXD_CLIENT_ID="your-client-id"
export LETTERBOXD_CLIENT_SECRET="your-client-secret"
```

Restart FirstRoll after changing environment variables. The film dossier enables **Load
Letterboxd** only when both credentials are present. FirstRoll uses the official OAuth token,
search and log-entry endpoints; it does not include an unofficial scraping fallback.

## Add a Private Study Library

Open `http://127.0.0.1:8000/settings` and use **Study library** to add PDF, EPUB,
Markdown or text documents. FirstRoll copies uploads into its private, Git-ignored managed
library. The same panel lists the current catalogue, removes registrations without deleting
the original source files, and rebuilds the local PDF search index. EPUB, Markdown and text
files are currently catalogue-only; Deep Study retrieval requires page-cited PDF content.

For a manual setup, create the private library folder and place documents inside it:

```bash
mkdir -p .firstroll/library
```

FirstRoll lists document titles, formats, sizes and broad study topics without returning
their paths to the browser. To make their actual content searchable, use **Rebuild search
index** in Settings, or build the private page-level index from the terminal:

```bash
uv run firstroll-index
```

Open a film dossier after the build completes. Discover will present substantial passages
selected for the study focus, with the source book and PDF page shown beside each one.
Rebuild the index whenever you add, remove or replace documents.

The index is stored at `.firstroll/library.sqlite3`. It contains stable token-bounded
chunks, SQLite full-text data and 384-dimensional multilingual vectors generated locally
with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. The first build
downloads the model; later retrieval is on-device. Set `FIRSTROLL_EMBEDDINGS=0` to build
an FTS-only fallback index. Original file paths are not returned
to the browser. The entire `.firstroll` directory is excluded from Git, so neither the
documents nor the derived index are published with the project.

Documents stored elsewhere can be registered in `.firstroll/library.json`:

```json
{
  "documents": [
    "/absolute/path/to/a/film-study-book.pdf",
    "/absolute/path/to/research-notes.md"
  ]
}
```

Rebuild the index after changing the library. Its current status is available in Settings or
at `http://127.0.0.1:8000/api/library/status`.

## Troubleshooting

### `uv: command not found`

Open a new terminal. If it is still unavailable, follow the official `uv` installation
instructions linked above.

### Port 8000 is already in use

Stop the other local service using port 8000, then run FirstRoll again. The frontend and
backend currently expect the same local origin.

### Film search says Wikidata is unavailable

Check the internet connection and try again. FirstRoll automatically falls back to its
small bundled offline catalogue for supported sample films.

### Enable the higher-quality TMDb catalogue

Create a TMDb application credential and copy its **API Read Access Token**. In local mode, open
**Settings → TMDb catalogue**, paste the token and run the connection test. Hosted deployments set
`TMDB_BEARER_TOKEN` only on the backend service; never put it in static frontend variables.

The token is optional. After it is saved, the same search interface automatically uses TMDb and
retains IMDb/Wikidata external IDs. Clearing it returns discovery to the open fallback. TMDb requires
attribution and separate review for commercial use.

### Video analysis fails but discovery works

Confirm that `ffmpeg -version` works in a new terminal. Start with a short MP4 clip;
large files and heavyweight model inference can require substantial memory.

### Settings returns `403`

Open Settings through `http://127.0.0.1:8000/settings`. It is intentionally blocked for
non-local clients.

## Privacy and Copyright

- FirstRoll binds to `127.0.0.1`; it does not accept connections from other devices.
- Connector secrets, when supported, are stored in `.firstroll/settings.json`, which is
  excluded from Git.
- Users are responsible for having permission to analyse uploaded clips and documents.
- Do not publish copyrighted books, films or clips merely because they are used in a
  private local research database.
