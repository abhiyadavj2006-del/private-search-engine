# private-search-engine

A private search engine in pure Python (standard library only).

It indexes a local corpus of documents on disk and ranks results with
TF-IDF — no external search engines, no network calls, no API keys,
no tracking. Your queries never leave your machine, because there is
nowhere for them to go.

This is project 4 of 5 in a series of five learning projects, but it is
a **standalone repo**: it runs on its own, with no dependency on the
other four projects. (Suggested GitHub repo name:
`private-search-engine`.)

## What it does

- **Indexes a local corpus** — Markdown / text / HTML files — into an
  in-memory inverted index.
- **Searches with ranking** — TF-IDF scoring, a ×3 boost for terms in
  a document's title, and a bonus for an exact-phrase match.
- **Returns snippets** — each result shows the matching passage, the
  file it came from, and its score.
- **Web UI** — a small search page on `http://localhost:8004/`, served
  by Python's `http.server`. No JavaScript framework, no build step.
- **Dynamic indexing** — the index is rebuilt from disk on every
  search and on every web request, so documents added later are found
  immediately, with no re-index step and no stale results.

## What is indexed

Two sources, both scanned at search time:

1. `corpus/` — six sample pages shipped with this repo, so the engine
   works out of the box:
   private search, Python standard library, Redis caching, databases
   and SQL, AI agents, C compiler basics.
2. The sibling projects' documentation (`../` — the `five-projects/`
   tree: `01-redis`, `02-database`, `03-ai-agent`, `05-c-compiler`),
   if present. When this was tested, the `03-ai-agent` notes were
   picked up automatically (see "What was tested"). Files added to
   those projects later are indexed too — nothing is cached on disk.

Only `.md`, `.txt`, `.html` / `.htm` files are indexed. `.py` source
files are deliberately excluded: this is a document search engine,
not a code search engine.

## How to run

Requirements: **Python 3.8+ only. No dependencies to install, no
Docker, no accounts.**

```bash
# 1. Clone (or copy) this repo and enter it
git clone <your-github-url> private-search-engine
cd private-search-engine

# 2a. Search from the command line
python3 search_engine.py search "private search"

# 2b. Or start the web UI (single command)
python3 search_engine.py serve
# → open http://localhost:8004/

# 2c. See what is indexed
python3 search_engine.py index

# 2d. Run the built-in smoke tests
python3 search_engine.py test
```

Port: `--port` wins, otherwise the `PORT` environment variable,
otherwise `8004`:

```bash
python3 search_engine.py serve --port 9000
PORT=9000 python3 search_engine.py serve
```

## What was tested

Tested 2026-11-21 on this machine (Python 3.12.3), by actually
running the program — all passed:

| Test | Command | Result |
|---|---|---|
| Indexing | `python3 search_engine.py index` | 15 documents, ~1,400 unique terms (6 sample pages + 9 docs found in the sibling projects — proving the dynamic scan works) |
| Smoke tests | `python3 search_engine.py test` | All passed: 5 queries return the expected page in the top 3, a nonsense query returns nothing |
| Query 1 | `search "private search"` | #1 private-search-engine (this README, score 40.5); #2 Private Search (corpus page, 22.5) |
| Query 2 | `search "redis caching"` | #1 Redis Caching (score 21.2) |
| Query 3 | `search "hiking checklist"` | #1 Hiking checklist — a file from the sibling `03-ai-agent` project, not this repo's own corpus |
| Query 4 | `search "c compiler"` | #1 c-compiler-in-c (the `05-c-compiler` README, score 42.4); C Compiler Basics in top 3 |
| No results | `search` with a nonsense word | `No results for "…".` (exit code 1) |
| Web UI home | `curl http://127.0.0.1:8004/` | 200, search form served |
| Web UI results | `curl "http://127.0.0.1:8004/?q=redis+caching"` | 200, "1 result(s) for redis caching", Redis Caching score 25.392 |
| Web UI 404 | `curl http://127.0.0.1:8004/nope` | 404 |
| `PORT` env var | `PORT=8009 python3 search_engine.py serve` | Served on 8009, not 8004 |
| `--port` override | `PORT=8009 … serve --port 8010` | Served on 8010 (`--port` wins over `PORT`) |
| Default port | `python3 search_engine.py serve` | Served on 8004 |

Note: exact scores shift slightly as sibling projects add documents,
because IDF depends on the total document count. That is expected —
the ranking is relative to the corpus at search time.

## Limitations — what this is not

- **Local corpus only.** It cannot search the web. For web search,
  use the SearXNG setup below.
- **In-memory index, rebuilt per search.** Fine for hundreds of
  documents; it would be slow for millions. There is no persistent
  on-disk index (nothing is written to disk — see `.gitignore`).
- **Simple ranking.** TF-IDF + title boost + phrase bonus. No
  stemming (so "searching" does not match "search"), no synonyms,
  no typo tolerance, no boolean operators, no faceting.
- **Single-user, no auth.** The web UI binds `0.0.0.0` (needed for
  hosted deployment) and has no login. Do not expose it to the
  internet without putting authentication in front of it.
- **Plain-text snippets only.** Results link to file paths, not to
  rendered pages.
- **English-oriented tokenising.** Non-Latin scripts are split on
  non-alphanumeric characters.

## Next steps to make it fuller

1. **Persistent index** — serialise the inverted index (e.g. SQLite
   FTS5) so startup is instant on a large corpus, and update it
   incrementally on file changes instead of rebuilding.
2. **Better ranking** — stemming, BM25 instead of raw TF-IDF, and
   field weights (title > headings > body).
3. **Search features** — phrase queries in quotes, `AND`/`OR`/`NOT`,
   typo-tolerant matching, result highlighting.
4. **Richer corpus** — point it at a notes folder, and add a file
   watcher so the UI reflects edits live.
5. **Caching** — cache rendered results for popular queries (this is
   where project 1, the Redis clone, fits in).
6. **Web search** — deploy SearXNG (below) when you need the web,
   and keep this engine for your own documents.

## The full version: SearXNG (web search, self-hosted)

This Python engine searches only local files. The full private
search engine — one that searches the **web** without tracking you —
is [SearXNG](https://docs.searxng.org/), a metasearch engine that
forwards queries to many public engines and strips identifying
information. It needs Docker, so it is **not** run here (Docker is
not installed on this machine), but the setup is included and ready:

- `docker-compose.yml` — SearXNG + Redis, bound to localhost only
  (`127.0.0.1:8080`)
- `searxng/settings.yml` — minimal private settings (local-only,
  limiter disabled, safe search on)

### SearXNG setup (on a machine with Docker)

```bash
# 1. Install Docker and Docker Compose, then copy this repo (or just
#    docker-compose.yml + searxng/) to the machine, e.g. ~/searxng/
# 2. Generate a secret key and store it in .env next to the compose file:
openssl rand -hex 32
#    then create .env containing:
#    SEARXNG_SECRET=<the hex string above>
# 3. Start it:
docker compose up -d
# 4. Open http://localhost:8080
# Update: docker compose pull && docker compose up -d
# Stop:   docker compose down
```

Never commit the `.env` file — it is in `.gitignore`. Do not expose
port 8080 publicly without adding authentication in front of it.

## Taking this project live

Nothing is deployed yet — this section is the checklist for when
Boss is ready. No GitHub remote exists for this repo yet; the repo
name and account are to be confirmed after GitHub is connected.

### The live demo is this web UI

The deployable piece is `search_engine.py serve`. It is a single
command, needs only Python 3, and respects the `PORT` environment
variable that hosts set automatically:

```bash
python3 search_engine.py serve
```

No build step, no dependencies to install, no database to provision,
no secrets or API keys. The corpus ships in `corpus/`, so the demo
works with zero configuration. (The sibling-projects scan simply
finds nothing extra when the repo stands alone — see below.)

### Hosting options

| Option | What is needed | Commands / notes |
|---|---|---|
| **Render** (free tier) | A Web Service, Python environment, start command `python3 search_engine.py serve`. Render sets `PORT` automatically. | Push repo to GitHub → Render → New Web Service → pick repo → start command as above. No env vars to set (optional: none). |
| **Railway** | Same as Render: it sets `PORT` and runs the start command. | `railway up` from the repo, or connect the GitHub repo; start command `python3 search_engine.py serve`. |
| **Fly.io** | `fly launch` with a Dockerfile (not included — would need a tiny one: `FROM python:3.12-slim`, copy files, `CMD ["python3", "search_engine.py", "serve"]`). Fly sets `PORT` (default 8080). | `fly launch` → `fly deploy`. |
| **Small VPS** (e.g. Hetzner, DigitalOcean) | Python 3, a process manager, a reverse proxy for HTTPS. | `python3 search_engine.py serve` behind `systemd` + Caddy/nginx; or `gunicorn` is unnecessary — stdlib server is enough for a demo, but put it behind a proxy for TLS and auth. |
| **PythonAnywhere / Replit** | A Python web app slot; run the same command as the entry point. | Follow the host's "run a script" flow; set `PORT` if the host requires a specific one. |

Environment variables: only `PORT` (optional; default `8004`).
No secrets, no database URL, no API keys.

### Before going live

1. Confirm the GitHub repo name (`private-search-engine` suggested)
   and create the repo; push this folder as its root.
2. Decide the corpus for the live demo: `corpus/` alone is enough.
   Note the engine also scans `../` (the parent folder) for sibling
   projects — on a host that folder is empty, so only `corpus/` is
   indexed. That is by design, not a bug.
3. Add basic auth / a login in front of the UI if the live URL is
   shared publicly (the UI currently has no auth).
4. Pick a host from the table above and deploy with the single
   command. Verify the live URL returns results for `private search`
   and `redis caching`.

## Repo layout

```
private-search-engine/
├── README.md            # this file
├── LICENSE              # MIT
├── .gitignore           # excludes generated index files, caches, .env
├── search_engine.py     # the whole engine: indexer, ranking, CLI, web UI
├── corpus/              # sample pages (the demo corpus)
│   ├── private-search.md
│   ├── python-stdlib.md
│   ├── redis-caching.md
│   ├── databases-sql.md
│   ├── ai-agents.md
│   └── c-compiler.md
├── docker-compose.yml   # SearXNG full version (needs Docker; not run here)
└── searxng/
    └── settings.yml     # SearXNG settings for the compose setup
```

## License

MIT — see [LICENSE](LICENSE).
