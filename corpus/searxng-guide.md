# SearXNG setup — NetworkChuck video guide

A private metasearch engine, from the video "ditch Google!! (build your
own PRIVATE search engine)" by NetworkChuck
(https://www.youtube.com/watch?v=ifT6npY39Dw).

## What a metasearch engine is

SearXNG keeps no index of its own. When you ask it for something, it
asks many public engines at once — Google, Bing, DuckDuckGo, Wikipedia,
Brave, Qwant and more — then merges all the answers into one result
page and removes the duplicates. That is the whole trick: you get
everyone's results without giving any one of them a profile of you.

## How it protects privacy

1. **Random profile per search.** Every query goes out with a fresh,
   random profile that has nothing to do with you. The upstream
   engines see a stranger searching, not you.
2. **No ads.** The results come back without advertising, because
   there is no ad network in the middle.
3. **No data shared with result sites.** Clicking a result does not
   hand your profile to that site.
4. **Your home IP stays home.** On a cloud server, the upstream
   engines see the server's public address, not your home address.
   On localhost this last benefit does not apply — the other three do.
5. **Public vs private.** A public instance can still be read by its
   owner (logs exist). The video's rule: don't trust anyone — run
   your own, keep it private, share it only with people you choose.

## Install (video steps, modern commands)

The video installs on an Ubuntu cloud server with Docker. The
commands below are the current equivalents — the video's old
`searxng-docker` repo is retired; the supported path is the compose
template in the main SearXNG repo (see `docker-compose.yml` here).

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git
mkdir -p ~/searxng/core-config && cd ~/searxng
# copy docker-compose.yml, .env.example and searxng/core-config/ here
cp .env.example .env
openssl rand -hex 32        # paste the output into .env as SEARXNG_SECRET
docker compose up -d
docker compose ps           # two containers: core + valkey
```

Open http://localhost:8080 and try a query. Stop everything with
`docker compose down`; bringing it back up pulls the latest images.

## Settings worth changing

Everything lives in `searxng/core-config/settings.yml` (see that file
here — every video tweak is annotated in it):

- **Back button fix (video 15:00).** The default HTTP method is POST,
  which breaks the browser back button. Set `server.method: "GET"`.
- **Instance name (15:40).** `general.instance_name` — the video
  uses "NetworkChuck Search".
- **Strict safe search (15:40).** `search.safe_search: 2`.
- **Autocomplete (15:40).** `search.autocomplete: "duckduckgo"`.
- **Stats (17:19).** `general.enable_metrics: true`, then open
  `/stats` to see per-engine response times and counts.
- **APIs (17:19).** Add `json` to `search.formats` and any program
  can query `GET /search?q=...&format=json` with no key.
- **Engines (15:40).** Over 70 engines in the video, 200+ today —
  disable any single one, for example Google, with
  `engines: [{name: google, disabled: true}]`.
- **Your own searchable sources (15:40).** SearXNG can query extra
  sources you add, even a local MySQL store. The Python engine in
  this repo mirrors that with `SEARCH_EXTRA_DIRS`.
- **Proxies and Tor (15:40).** Possible per-search, covered in the
  SearXNG docs rather than in the video.

## What this page is for

This file is part of the local engine's corpus, so the Python search
engine can answer questions about the SearXNG setup itself. Try
`python3 search_engine.py search "back button"` or
`search "safe search"`.
