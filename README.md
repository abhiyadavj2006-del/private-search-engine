# private-search-engine

A private search engine in pure Python (standard library only) — plus
the full self-hosted SearXNG setup from the video that inspired it.

It indexes a local corpus of documents on disk and ranks results with
TF-IDF — no external search engines, no network calls, no API keys,
no tracking. Your queries never leave your machine, because there is
nowhere for them to go.

This is project 4 of 5 in a series of five learning projects, but it is
a **standalone repo**: it runs on its own, with no dependency on the
other four projects. (Suggested GitHub repo name:
`private-search-engine`.)

## Source

**Video:** "ditch Google!! (build your own PRIVATE search engine)" by
NetworkChuck — https://www.youtube.com/watch?v=ifT6npY39Dw

**What the video teaches** (from the video page, its chapter list, and
its full transcript, read via youtubetotranscript.com — the video was
not watched in a player, so anything below that is not in the
transcript or the docs is marked as such):

| Video chapter | What it teaches | Where it lives here |
|---|---|---|
| 3:15 What is Searx and why is it awesome? | SearXNG is a **metasearch** engine: it asks Google, Bing, DuckDuckGo, Wikipedia… all at once and merges the answers. Privacy comes from a **random search profile per search**, **no ads**, **no data shared with result sites**, and the **server's IP hiding your home IP**. Public vs private instances: a public instance's owner can still read logs — "don't trust anyone, only yourself." | `search_engine.py` mirrors the architecture locally (see below); `corpus/searxng-guide.md` explains it |
| 7:00 Build our server | Linode cloud server, Ubuntu 20.04, SSH, `apt update && apt upgrade`, Docker + docker-compose + git | README SearXNG setup below |
| 9:30 How to install Searx | `git clone searxng-docker`, edit hidden `.env` (domain + Let's Encrypt email for SSL), generate a **secret key** into settings, `docker-compose up -d` → 3 containers: **caddy, searxng, redis** | `docker-compose.yml` (modernised — see note) |
| 12:00 Testing | Search "coffee", results show their source engines; home-lab option: default `.env` → `localhost:8080` (IP privacy benefit lost, the rest kept) | `docker-compose.yml` + `searxng/core-config/settings.yml` |
| 13:24 Tearing it all down | `docker-compose down`; bringing it back up updates the containers | Same commands, modern spelling |
| 15:00 Fixing the back button issue | Default HTTP method is **POST**, which breaks the back button → set `server.method: "GET"` in settings.yml | `searxng/core-config/settings.yml` (`method: "GET"`); the local web UI uses a GET form too |
| 15:40 Cool features | `general.instance_name`, **enable metrics**, **strict safe search (2)**, **autocomplete (DuckDuckGo)**; **70+ engines** enable/disable individually; **add your own searchable databases** (e.g. local MySQL); **proxies / Tor** per search | `searxng/core-config/settings.yml`; local equivalents in `search_engine.py` |
| 17:19 Checking stats + APIs | `/stats` page (enable metrics first); SearXNG "also has APIs" (JSON) | `/stats` endpoint + `?format=json` in `search_engine.py`; `formats: [html, json]` in settings.yml |

**One honest correction:** the video is from 2022 and its exact
commands target the old `searxng-docker` repo, which is now
**deprecated**. The current upstream way is the "compose instancing"
template in the main SearXNG repo (`core` + `valkey`, no bundled
Caddy). This project follows the **current** template and maps each
video step to its modern equivalent in `docker-compose.yml` and
`.env.example` — the video's ideas are unchanged, only the commands
moved on. SearXNG itself is also bigger now: 200+ engines instead of
the video's "over 70".

## What it does (advanced)

- **Metasearch, locally** — like SearXNG queries many upstream
  engines, this engine queries several independent engines and
  **merges + dedupes** the results, tagging each result with the
  engine(s) that returned it:
  - `corpus` — the sample pages in `corpus/` (the demo corpus)
  - `projects` — docs of the sibling projects (your "own database")
  - `extra` — folders from `SEARCH_EXTRA_DIRS`, if you add any
- **Bangs** — `!corpus redis` / `!projects python` scope a query to
  one engine, like SearXNG's `!images` / `!wikipedia`.
- **JSON API** — `?format=json` on the web UI, or
  `search "…" --json` on the CLI. (The video: SearXNG "also has APIs".)
- **Autocomplete** — `/autocomplete?q=priv` suggests terms from the
  index (mirrors the video's autocomplete setting).
- **Stats** — `/stats` (HTML or `?format=json`) and the `stats`
  command show index size, uptime, queries served, cache hits, top
  queries, results per engine (mirrors the video's `/stats` chapter).
- **Safe search** — levels 0/1/2 via `?safe_search=` or `--safe-search`
  (default 1; SearXNG side uses 2, strict, exactly as in the video).
- **Privacy headers + GET forms** — every response sends
  `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`,
  `X-Robots-Tag: noindex, nofollow`; the search form uses GET, which
  is the video's back-button fix applied to this UI.
- **Instance name** — `INSTANCE_NAME` env var (default
  "Private Search"), mirroring `general.instance_name`.
- **Your own searchable sources** — `SEARCH_EXTRA_DIRS` adds folders
  as a third engine (the video's "add your own databases").
- **Result cache** — repeated queries are served from an in-memory
  cache (`SEARCH_CACHE_TTL`, default 60 s, 0 disables).
- **Dynamic indexing** — the index is rebuilt from disk on every
  search and on every web request, so documents added later are found
  immediately, with no re-index step and no stale results.

## What is indexed

Three sources, all scanned at search time:

1. `corpus/` — seven sample pages shipped with this repo, so the
   engine works out of the box: private search, Python standard
   library, Redis caching, databases and SQL, AI agents, C compiler
   basics, and the SearXNG video guide.
2. The sibling projects' documentation (`../` — the `five-projects/`
   tree: `01-redis`, `02-database`, `03-ai-agent`, `05-c-compiler`),
   if present. Files added to those projects later are indexed too —
   nothing is cached on disk.
3. `SEARCH_EXTRA_DIRS` — extra folders you point the engine at
   (colon-separated on Linux/macOS, `;` on Windows).

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
python3 search_engine.py search "!corpus back button"   # one engine only
python3 search_engine.py search "private search" --json  # JSON API output
python3 search_engine.py search "coffee" --engines corpus,projects

# 2b. Or start the web UI (single command)
python3 search_engine.py serve
# → open http://localhost:8004/

# 2c. See what is indexed (per engine)
python3 search_engine.py index

# 2d. Autocomplete + stats from the CLI
python3 search_engine.py autocomplete priv
python3 search_engine.py stats

# 2e. Run the built-in tests (6 baseline + 9 advanced checks)
python3 search_engine.py test
```

Port: `--port` wins, otherwise the `PORT` environment variable,
otherwise `8004`:

```bash
python3 search_engine.py serve --port 9000
PORT=9000 python3 search_engine.py serve
```

Environment variables: `PORT` (default `8004`), `INSTANCE_NAME`
(default `Private Search`), `SAFE_SEARCH` (0/1/2, default 1),
`SEARCH_CACHE_TTL` (seconds, default 60, 0 disables),
`SEARCH_EXTRA_DIRS` (extra corpus folders). No secrets, no database
URL, no API keys.

### Web UI endpoints

| Endpoint | What it does |
|---|---|
| `GET /?q=…` | Search page (HTML). `&format=json` for the JSON API, `&engines=corpus,projects` to pick engines, `&safe_search=0/1/2` for safe search. Bangs work in `q` too. |
| `GET /autocomplete?q=…` | JSON term suggestions, e.g. `{"query": "priv", "suggestions": ["private", …]}` |
| `GET /stats` | Stats page (HTML, `?format=json` for JSON): docs, uptime, queries, cache hits, top queries |

## What was tested

Tested 2026-11-22 on this machine (Python 3.12.3), by actually
running the program — all passed:

| Test | Command | Result |
|---|---|---|
| Indexing | `python3 search_engine.py index` | 20 documents, 1,851 unique terms (7 sample pages + 13 docs from the sibling projects) |
| Full test suite | `python3 search_engine.py test` | **All 15 checks passed** (6 baseline + 9 advanced): 5 queries return the expected page in the top 3, a nonsense query returns nothing, engine scoping, bangs, JSON, autocomplete, safe search, extra dirs, cache, and 6 live web-endpoint checks |
| Query 1 | `search "private search"` | #1 private-search-engine (this README, score 40.1); #2 Private Search (corpus page, 20.0) |
| Query 2 | `search "redis caching"` | #1 Build Your Own Redis — in Java (score 20.0); Redis Caching in top 3 |
| Query 3 | `search "!corpus back button"` | #1 SearXNG setup — NetworkChuck video guide (corpus engine only) |
| Query 4 | `search "private search" --json` | Valid JSON, 10 results, each tagged with its engine |
| Autocomplete | `autocomplete priv` / `autocomplete sea` | `private`, … / `search, searches, searxng, …` |
| Stats | `python3 search_engine.py stats` | 20 docs, 1,851 terms, corpus: 7, projects: 13 |
| Web UI home | `curl http://127.0.0.1:8009/` (via `PORT=8009`) | 200, search form served, `Referrer-Policy: no-referrer` header present |
| Web UI JSON | `curl "http://127.0.0.1:8009/?q=back+button&format=json"` | 200, 8 results, #1 SearXNG video guide |
| Autocomplete API | `curl "http://127.0.0.1:8009/autocomplete?q=sea"` | 200, suggestions include `search`, `searxng` |
| Stats API | `curl http://127.0.0.1:8009/stats?format=json` | 200, documents 20, queries counted |
| Web UI 404 | `curl http://127.0.0.1:8009/nope` | 404 |
| `PORT` env var | `PORT=8009 python3 search_engine.py serve` | Served on 8009, not 8004 |
| `--port` override | `PORT=8009 … serve --port 8010` | Served on 8010 (`--port` wins over `PORT`) |
| SearXNG YAML | `python3 -c "yaml.safe_load(...)"` on both files | `docker-compose.yml` (services `core` + `valkey`) and `searxng/core-config/settings.yml` parse; `method: GET`, `safe_search: 2`, `formats: [html, json]`, `enable_metrics: true`, no `secret_key` in the file |

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
- **In-memory result cache only.** Restarting the server clears it;
  there is no shared cache (the SearXNG stack uses Valkey for that).
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
not installed on this machine), but the setup is included, ready,
and aligned with the current upstream docs:

- `docker-compose.yml` — SearXNG `core` + `valkey`, bound to
  localhost only (`127.0.0.1:8080`)
- `.env.example` — copy to `.env`, put your generated secret in it
- `searxng/core-config/settings.yml` — video-faithful settings:
  `method: "GET"` (back-button fix), `safe_search: 2` (strict),
  `autocomplete: "duckduckgo"`, `enable_metrics: true` (`/stats`),
  `formats: [html, json]` (the JSON API), `limiter: true`,
  `image_proxy: true`, `instance_name: "Private Search"`

### SearXNG setup (on a machine with Docker)

```bash
# 1. Install Docker and Docker Compose, then copy this repo (or just
#    docker-compose.yml + .env.example + searxng/) to the machine
# 2. Copy the env template and generate a secret key:
cp .env.example .env
openssl rand -hex 32
#    then paste the output into .env as:  SEARXNG_SECRET=<hex string>
# 3. Start it:
docker compose up -d
# 4. Open http://localhost:8080  (try a search — e.g. "coffee",
#    the video's example — and look at the source engines listed)
# Check:  docker compose ps      (two containers: core + valkey)
# Update: docker compose pull && docker compose up -d
# Stop:   docker compose down
# Logs:   docker compose logs -f core
```

Never commit the `.env` file — it is in `.gitignore`. Never paste a
real secret into `settings.yml` (the file is committed; the secret
lives only in `.env` as `SEARXNG_SECRET`). Do not expose port 8080
publicly without adding authentication in front of it.

### Domain + HTTPS (the video's optional step)

The video set a domain + Let's Encrypt email in `.env` because the
old stack bundled Caddy. The current template does not bundle a
reverse proxy, so for a public domain you run your own in front of
`http://localhost:8080` (Caddy or nginx) and set
`server.base_url: "https://your-domain/"` in
`searxng/core-config/settings.yml`. Caddy example (on the Docker
host, after SearXNG is up):

```
# Caddyfile
search.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Point your domain's A record at the server's public IP first (the
video's domain step), then Caddy issues the certificate for you.

## What changed in this update (2026-11-22)

From starter to advanced, following the NetworkChuck video's actual
content (transcript + chapters) and the current SearXNG docs:

- **SearXNG setup modernised:** old `searxng-docker` layout
  (3 containers, `redis`, `searxng/settings.yml`, `SEARXNG_BASE_URL`
  env) replaced with the current upstream compose template
  (`core` + `valkey`, `searxng/core-config/settings.yml`,
  `.env.example` with `SEARXNG_HOST`/`SEARXNG_PORT`/`SEARXNG_SECRET`).
- **Settings now implement the video's chapters:** `method: "GET"`
  (back-button fix), `safe_search: 2`, `autocomplete: "duckduckgo"`,
  `enable_metrics: true` (`/stats`), `formats: [html, json]`
  (JSON API), `limiter: true` (now that Valkey exists),
  `image_proxy: true`, commented engine-disable + proxy examples.
- **Local engine is now a metasearch engine:** per-engine scoring
  (`corpus` / `projects` / `extra`), merge + dedupe, engine tags on
  results, `!bang` scoping, `--engines` selection.
- **New features:** JSON API, autocomplete endpoint + CLI, `/stats`
  + `stats` command, safe search levels, privacy headers, instance
  name, `SEARCH_EXTRA_DIRS`, result cache.
- **New corpus page** `corpus/searxng-guide.md` summarising the
  video, so the engine can answer questions about the SearXNG setup
  itself (try `search "back button"`).
- **Tests grew from 6 to 15 checks**, all passing; the original 6
  baseline checks are unchanged and still pass.

## What was intentionally left out, and why

- **Running SearXNG itself** — needs Docker; Docker is not installed
  on this machine, and the brief forbids nothing else, but there is
  no Docker host here to run it on. The compose files are validated
  (YAML parses, keys asserted) but not executed. Run them on any
  machine with Docker using the steps above.
- **A public/cloud deployment of SearXNG** — the video deploys to a
  Linode server with a domain and SSL. That needs a cloud account,
  a server, and a domain; no accounts were created for this project.
  The localhost setup is complete; the domain/HTTPS step is
  documented above instead.
- **Caddy bundled in the compose file** — the video's stack had it,
  the current upstream template does not. Adding a third container
  would diverge from the supported template; the reverse proxy is
  documented as a separate step instead.
- **Tor / outgoing proxies in SearXNG** — the video mentions them
  but explicitly does not cover them ("that'll make this video way
  too long"). They are a commented pointer in `settings.yml`, not
  enabled.
- **A real secret key** — none is generated or committed. The setup
  requires the user to run `openssl rand -hex 32` once and paste it
  into `.env`. Shipping a pre-made secret would be worse than none.
- **Stemming / BM25 / typo tolerance in the local engine** — not in
  the video, and the README's "Next steps" already lists them as
  future work. The ranking is unchanged (TF-IDF + title boost +
  phrase bonus) so the baseline checks still pass.

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
├── README.md                  # this file
├── LICENSE                    # MIT
├── .gitignore                 # excludes caches, .env (never commit it)
├── search_engine.py           # the whole engine: metasearch, ranking,
│                              # CLI, JSON API, autocomplete, /stats, web UI
├── corpus/                    # sample pages (the demo corpus)
│   ├── private-search.md
│   ├── python-stdlib.md
│   ├── redis-caching.md
│   ├── databases-sql.md
│   ├── ai-agents.md
│   ├── c-compiler.md
│   └── searxng-guide.md       # the NetworkChuck video, summarised
├── docker-compose.yml         # SearXNG full version (needs Docker; not run here)
├── .env.example               # copy to .env, add your SEARXNG_SECRET
└── searxng/
    └── core-config/
        └── settings.yml       # SearXNG settings for the compose setup
```

## License

MIT — see [LICENSE](LICENSE).
