# Deploy on PythonAnywhere (free Beginner tier)

PythonAnywhere runs web apps through **WSGI**, not via
`python3 search_engine.py serve`. `pythonanywhere_wsgi.py` (in this
repo) adapts the existing stdlib server to WSGI without changing
the app.

## 1. Create the account

`pythonanywhere.com` -> "Create a Beginner account" (free, **no
card**). Pick the username carefully: your site will be
`https://USERNAME.pythonanywhere.com/`.

> **One free account = one web app.** A Beginner account hosts a
> single web app (confirmed on PythonAnywhere's own pricing page;
> even the $10/month Developer plan allows only one — only Custom
> plans allow more). To host both this search engine and the AI
> agent for free you need **two free accounts** (two subdomains),
> or one combined app (see "Two apps, one account" below), or a
> paid Custom plan.

## 2. Get the code on the server

Open a **Bash console** from the dashboard and clone this repo:

```bash
git clone https://github.com/abhiyadavj2006-del/private-search-engine.git
cd private-search-engine
python3 --version   # use the same version for the web app below
```

No dependencies to install (stdlib only), no virtualenv needed.
(The `docker-compose.yml` / SearXNG setup in this repo needs
Docker and does **not** run on PythonAnywhere — only the Python
engine in `search_engine.py` is deployed here.)

## 3. Create the web app

Web tab -> **Add a new web app** -> choose the free domain
(`USERNAME.pythonanywhere.com`) -> **Manual configuration** ->
pick **Python 3.12** (or the newest offered; the code needs 3.10+).

Then in the Web tab set:

| Setting          | Value                                              |
| ---------------- | -------------------------------------------------- |
| Source code      | `/home/USERNAME/private-search-engine`             |
| Working directory| `/home/USERNAME/private-search-engine`             |
| Virtualenv       | (leave blank — stdlib only, nothing to install)    |

## 4. Point the WSGI file at this repo

Click the **WSGI configuration file** link in the Web tab (a file
like `/var/www/USERNAME_pythonanywhere_com_wsgi.py`) and replace
its contents with:

```python
import sys
sys.path.insert(0, '/home/USERNAME/private-search-engine')
from pythonanywhere_wsgi import application
```

Replace `USERNAME` with your PythonAnywhere username. Then hit
**Reload** and visit `https://USERNAME.pythonanywhere.com/`.

## 5. Static files

None — every page is generated HTML; there are no CSS/JS/image
assets to map.

## What lives where (data)

- **Corpus is read from disk.** The index is rebuilt from
  `corpus/` (and sibling docs, see below) on **every request** —
  exactly like `serve` does locally — so files added later show
  up immediately. No database, nothing to provision.
- **The `projects` engine** indexes the sibling projects under
  the parent folder. On PythonAnywhere that folder only holds what
  you clone there, so clone the other four repos next to this one
  if you want their docs searchable too — or leave it: the
  `corpus` engine alone is the demo corpus.
- **No outbound network calls.** The engine never contacts the
  internet, so the free tier's restricted outbound whitelist does
  not affect it.
- **CPU budget:** 100 CPU-seconds/day on the free tier. The
  per-request index rebuild walks the whole corpus tree, so each
  search costs some CPU — fine for demo traffic, but do not expect
  hundreds of searches a day on the free allowance.
- **No auth.** Anyone with the URL can search. Do not share the
  URL publicly unless you add a login in front of it.

## Two apps, one account (options)

- **Two free accounts** (simplest, no code changes): one account
  for this search engine, a second for the AI agent. Two
  subdomains.
- **One combined app:** a single WSGI app that routes by path
  prefix (e.g. `/` -> search engine, `/agent` -> AI agent). Needs
  a small dispatcher file — not written yet; ask for it if wanted.
- **Paid Custom plan** ($10+/month): up to 20 web apps on one
  account.

## Local test (no account needed)

```bash
python3 pythonanywhere_wsgi.py   # http://127.0.0.1:8000
```
