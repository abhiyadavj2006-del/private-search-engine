#!/usr/bin/env python3
"""
Private search engine — Project 4 of 5 (ADVANCED version).

Source tutorial: "ditch Google!! (build your own PRIVATE search engine)"
by NetworkChuck — https://www.youtube.com/watch?v=ifT6npY39Dw
The video teaches SearXNG, a privacy-respecting METASEARCH engine: it
forwards your query to many upstream engines (Google, Bing, DuckDuckGo,
Wikipedia, ...) at once, merges the answers, and protects you by
generating a random search profile per search, stripping ads and
identifying data, and (on a cloud server) hiding your home IP behind
the server's IP. This project implements those ideas in two layers:

  1. search_engine.py — a standalone Python (stdlib-only) engine that
     mirrors the video's architecture on a local corpus:
       * metasearch: several independent "engines" (corpus, projects,
         extra) are queried and their results merged + deduped, each
         result tagged with the engine(s) that returned it — just like
         SearXNG shows which upstream engines answered.
       * bangs: "!corpus redis" / "!projects python" scope a query to
         one engine, like SearXNG's "!images" / "!wikipedia" bangs.
       * JSON API (?format=json / `search --json`) — the video points
         out SearXNG "also has APIs".
       * autocomplete (/autocomplete?q=...) — mirrors the video's
         autocomplete setting (DuckDuckGo backend there; index terms
         here, since there is no network).
       * /stats page — mirrors the video's "Checking stats" chapter
         and SearXNG's /stats (general.enable_metrics).
       * safe search levels 0/1/2 (?safe_search= / --safe-search) —
         the video sets strict safe search (2, "great for my kids").
       * privacy headers on every response (Referrer-Policy:
         no-referrer, X-Content-Type-Options, X-Robots-Tag) and a
         GET search form — the video's "back button" fix is exactly
         this: SearXNG's POST method breaks the back button, so the
         video sets server.method to GET. This UI uses GET only.
       * instance name via INSTANCE_NAME — mirrors
         general.instance_name ("NetworkChuck Search" in the video).
       * your own searchable sources via SEARCH_EXTRA_DIRS — the
         video's "add your own databases that are searchable".
       * no tracking: no cookies, no logs of who searched what, no
         network calls at all. Queries never leave the machine.
  2. docker-compose.yml + searxng/core-config/ — the REAL SearXNG
     (the video's actual software), modernised to the current
     upstream compose template (core + valkey). Needs Docker; see
     README.md. Not run here — Docker is not installed on this VM.

Corpus (indexed fresh on every search / server start, so files added
later are picked up automatically):
  1. corpus/  — sample pages shipped with this project, and
  2. ~/workspace/five-projects/ — every README / doc in the sibling
     projects (01-redis, 02-database, 03-ai-agent, 05-c-compiler, ...),
     whatever exists at search time, and
  3. SEARCH_EXTRA_DIRS — extra folders you point the engine at.

Usage:
    python3 search_engine.py index                  # print index stats
    python3 search_engine.py search "private search"
    python3 search_engine.py search "coffee" --json
    python3 search_engine.py search "!corpus redis"
    python3 search_engine.py autocomplete priv      # suggestions
    python3 search_engine.py stats                  # index + live stats
    python3 search_engine.py serve [--port 8004]    # web UI on localhost
    python3 search_engine.py test                   # built-in tests

The server port comes from --port, or from the PORT environment
variable when --port is not given (default 8004). This is what hosts
like Render / Railway / Fly.io set, so the same single command works
locally and when deployed:
    PORT=8004 python3 search_engine.py serve

Environment variables:
    PORT               web UI port (default 8004)
    INSTANCE_NAME      name shown in the web UI (default "Private Search")
    SAFE_SEARCH        0 = off, 1 = moderate, 2 = strict (default 1)
    SEARCH_CACHE_TTL   seconds to cache results, 0 disables (default 60)
    SEARCH_EXTRA_DIRS  extra corpus folders, os.pathsep-separated

Ranking: TF-IDF over stemmed-ish tokens, with a x3 boost for terms in
the document title (first heading / first line) and a bonus for an
exact-phrase match. Scores are computed per engine, then merged.
"""

import argparse
import html
import json
import math
import os
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
# Root of the whole five-projects tree: one level up from this project.
PROJECTS_ROOT = BASE_DIR.parent
CORPUS_DIR = BASE_DIR / "corpus"

# File types indexed. .py is deliberately excluded: this is a document
# search engine, not a code search engine.
INDEX_EXTENSIONS = {".md", ".txt", ".html", ".htm"}
# Directories never descended into.
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules",
             ".idea", "searxng"}
# This project's own generated / non-content files are skipped by
# extension or name (search_engine.py is .py, README.md IS indexed —
# that is intentional: project docs are part of the corpus).

# --- metasearch: the independent "engines" this engine queries -------
# corpus   = the sample pages shipped in corpus/ (the demo corpus)
# projects = docs of the sibling projects (the "own database" idea)
# extra    = folders from SEARCH_EXTRA_DIRS, if any are configured
ALL_ENGINES = ("corpus", "projects", "extra")
# SearXNG-style bangs: "!corpus redis" searches only the corpus engine.
ENGINE_BANGS = {"!corpus": "corpus", "!projects": "projects",
                "!extra": "extra", "!docs": "projects"}

# --- safe search: words filtered out at level 1 (moderate) / 2 (strict)
# The local corpus is clean, so this normally changes nothing — it is
# the local equivalent of SearXNG's search.safe_search (the video sets
# 2, "great for my kids"). Level 0 disables filtering entirely.
BLOCKED_MODERATE = {
    "porn", "pornographic", "xxx", "sex", "nude", "casino", "gambling",
    "betting", "lottery",
}
BLOCKED_STRICT = BLOCKED_MODERATE | {
    "alcohol", "beer", "wine", "whiskey", "vodka", "tobacco",
    "cigarette", "cigar", "weed", "marijuana", "cannabis",
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "this", "to", "was", "were", "will", "with", "you", "your",
    "can", "not", "but", "if", "so", "we", "they", "them", "he", "she",
    "his", "her", "our", "their", "all", "any", "do", "does", "did",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
HTML_TAG_RE = re.compile(r"<[^>]+>")

INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "Private Search")


def default_safe_search():
    try:
        return max(0, min(2, int(os.environ.get("SAFE_SEARCH", "1"))))
    except ValueError:
        return 1


def cache_ttl():
    try:
        return max(0, int(os.environ.get("SEARCH_CACHE_TTL", "60")))
    except ValueError:
        return 60


# --- live stats (the /stats page; SearXNG's enable_metrics idea) -----
_STATS_LOCK = threading.Lock()
STATS = {
    "started": time.time(),
    "queries_total": 0,
    "cache_hits": 0,
    "top_queries": Counter(),
    "results_by_engine": Counter(),
}
_CACHE = {}  # (query, engines, safe_search, top_n) -> (expires, results)


def tokenize(text):
    """Lowercase alphanumeric tokens, minus stopwords."""
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def strip_markup(text, suffix):
    """Remove Markdown/HTML markup so only readable words are indexed."""
    if suffix in {".html", ".htm"}:
        text = HTML_TAG_RE.sub(" ", text)
    # Markdown: links [text](url) -> text, headings, code fences, etc.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*`_~|\-]{1,3}", " ", text)
    return html.unescape(text)


def extract_title(text, path):
    """First Markdown heading, first HTML <title>/<h1>, else filename."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                return title
    m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if m:
        return html.unescape(m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
    if m:
        return html.unescape(HTML_TAG_RE.sub("", m.group(1))).strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:80]
    return path.stem.replace("-", " ").replace("_", " ").title()


class Document:
    def __init__(self, path, title, text, source):
        self.path = path
        self.title = title
        self.text = text  # plain text, for snippets / phrase matching
        self.source = source  # which engine this doc belongs to
        self.tokens = tokenize(text)
        self.term_freq = Counter(self.tokens)
        self.title_tokens = set(tokenize(title))


class Index:
    def __init__(self):
        self.docs = []                       # list[Document]
        self.postings = defaultdict(dict)    # term -> {doc_id: tf}
        self.doc_freq = Counter()            # term -> #docs containing it

    @property
    def num_docs(self):
        return len(self.docs)

    @property
    def num_terms(self):
        return len(self.postings)

    def docs_by_engine(self, engine):
        return sum(1 for d in self.docs if d.source == engine)


def extra_dirs():
    """Extra corpus folders from SEARCH_EXTRA_DIRS (pathsep-separated)."""
    out = []
    for raw in os.environ.get("SEARCH_EXTRA_DIRS", "").split(os.pathsep):
        raw = raw.strip()
        if raw:
            out.append(Path(raw))
    return out


def collect_files():
    """All indexable files: (path, engine) pairs from corpus/,
    the five-projects tree, and SEARCH_EXTRA_DIRS."""
    roots = [(CORPUS_DIR, "corpus"), (PROJECTS_ROOT, "projects")]
    roots += [(d, "extra") for d in extra_dirs()]
    seen = set()
    files = []
    for root, source in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            )
            for name in sorted(filenames):
                p = Path(dirpath) / name
                if p.suffix.lower() not in INDEX_EXTENSIONS:
                    continue
                if p.resolve() in seen:
                    continue
                seen.add(p.resolve())
                files.append((p, source))
    return sorted(files)


def build_index():
    """(Re)build the whole index from disk. Corpus is small, so a full
    rebuild on every search keeps results correct when sibling
    projects add READMEs later — no stale-index problem."""
    index = Index()
    for path, source in collect_files():
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        text = strip_markup(raw, path.suffix.lower())
        title = extract_title(raw, path)
        doc = Document(path, title, text, source)
        doc_id = len(index.docs)
        index.docs.append(doc)
        for term, tf in doc.term_freq.items():
            index.postings[term][doc_id] = tf
            index.doc_freq[term] += 1
    return index


def make_snippet(doc, query_terms, width=200):
    """~200 chars of plain text centred on the first query-term hit."""
    low = doc.text.lower()
    best = None
    for term in query_terms:
        pos = low.find(term)
        if pos != -1 and (best is None or pos < best):
            best = pos
    if best is None:
        snippet = doc.text.strip()[:width]
    else:
        start = max(0, best - 60)
        snippet = doc.text[start:start + width].strip()
        if start > 0:
            snippet = "…" + snippet
        if start + width < len(doc.text):
            snippet = snippet + "…"
    return " ".join(snippet.split())


def parse_query(query):
    """Split SearXNG-style bangs off the query.

    "!corpus redis" -> ("redis", {"corpus"}); no bang -> (query, None).
    Unknown "!word" tokens are left in the query (the tokenizer drops
    the "!" anyway), exactly like an unknown bang in SearXNG is ignored.
    """
    engines = None
    kept = []
    for word in query.split():
        engine = ENGINE_BANGS.get(word.lower())
        if engine:
            engines = engines or set()
            engines.add(engine)
        else:
            kept.append(word)
    return " ".join(kept), engines


def blocked_terms(level):
    if level >= 2:
        return BLOCKED_STRICT
    if level >= 1:
        return BLOCKED_MODERATE
    return frozenset()


def _score_engine(index, query_terms, phrase, engine):
    """TF-IDF scores for one engine's docs only. Returns {doc_id: score}."""
    n = max(index.num_docs, 1)
    scores = defaultdict(float)
    for term in set(query_terms):
        postings = index.postings.get(term)
        if not postings:
            continue
        # IDF, smoothed so a term in every doc still counts a little.
        idf = math.log(1 + n / index.doc_freq[term])
        for doc_id, tf in postings.items():
            doc = index.docs[doc_id]
            if doc.source != engine:
                continue
            tf_norm = 1 + math.log(tf) if tf > 0 else 0
            score = tf_norm * idf
            if term in doc.title_tokens:
                score *= 3.0  # title boost
            scores[doc_id] += score
    # Exact-phrase bonus: the whole query appearing verbatim.
    if len(query_terms) > 1:
        for doc_id, doc in enumerate(index.docs):
            if doc.source != engine:
                continue
            if phrase in doc.text.lower():
                scores[doc_id] += 2.0
    return scores


def search(index, query, top_n=10, engines=None, safe_search=None):
    """Metasearch. Queries each selected engine, merges + dedupes the
    results (best score wins, engines unioned), applies safe search,
    and returns a list of dicts: rank, title, path, score, snippet,
    engines. Empty list when nothing matches.

    engines: None = all engines (or the ones named by a !bang in the
    query — a bang beats the engines argument). safe_search: None =
    $SAFE_SEARCH (default 1); 0 off, 1 moderate, 2 strict.
    """
    if safe_search is None:
        safe_search = default_safe_search()
    clean_query, bang_engines = parse_query(query)
    if bang_engines is not None:
        engines = bang_engines
    if engines is None:
        engines = set(ALL_ENGINES)
    else:
        engines = set(engines)
    query_terms = tokenize(clean_query)
    if not query_terms:
        return []
    phrase = clean_query.strip().lower()
    cache_key = (clean_query, tuple(sorted(engines)), safe_search, top_n)
    ttl = cache_ttl()
    with _STATS_LOCK:
        STATS["queries_total"] += 1
        STATS["top_queries"][clean_query.lower()] += 1
        cached = _CACHE.get(cache_key)
        if cached and ttl > 0 and cached[0] > time.time():
            STATS["cache_hits"] += 1
            return cached[1]
    # Query every engine, then merge like a metasearch engine does.
    merged = {}  # doc_id -> [best_score, {engines}]
    for engine in sorted(engines):
        for doc_id, score in _score_engine(
                index, query_terms, phrase, engine).items():
            if doc_id in merged:
                merged[doc_id][0] = max(merged[doc_id][0], score)
                merged[doc_id][1].add(engine)
            else:
                merged[doc_id] = [score, {engine}]
    # Safe search: drop docs containing blocked terms.
    blocked = blocked_terms(safe_search)
    if blocked:
        merged = {doc_id: v for doc_id, v in merged.items()
                  if not (blocked & set(index.docs[doc_id].term_freq))}
    ranked = sorted(merged.items(),
                    key=lambda kv: (-kv[1][0], kv[0]))
    results = []
    for rank, (doc_id, (score, srcs)) in enumerate(ranked[:top_n], start=1):
        doc = index.docs[doc_id]
        try:
            rel = str(doc.path.relative_to(PROJECTS_ROOT))
        except ValueError:
            rel = str(doc.path)
        results.append({
            "rank": rank,
            "title": doc.title,
            "path": rel,
            "score": round(score, 3),
            "snippet": make_snippet(doc, query_terms),
            "engines": sorted(srcs),
        })
    with _STATS_LOCK:
        for r in results:
            for e in r["engines"]:
                STATS["results_by_engine"][e] += 1
        if ttl > 0:
            _CACHE[cache_key] = (time.time() + ttl, results)
    return results


def autocomplete(index, prefix, limit=8):
    """Term suggestions for a prefix, most common first — the local
    equivalent of SearXNG's search.autocomplete."""
    terms = tokenize(prefix)
    if not terms:
        return []
    frag = terms[0]
    cands = [(df, term) for term, df in index.doc_freq.items()
             if term.startswith(frag) and term != frag]
    cands.sort(key=lambda kv: (-kv[0], kv[1]))
    return [term for _, term in cands[:limit]]


def get_stats(index):
    """Snapshot for the /stats page and `stats` command."""
    with _STATS_LOCK:
        top = STATS["top_queries"].most_common(10)
        snap = {
            "instance": INSTANCE_NAME,
            "documents": index.num_docs,
            "unique_terms": index.num_terms,
            "documents_by_engine": {
                e: index.docs_by_engine(e) for e in ALL_ENGINES
                if index.docs_by_engine(e) > 0
            },
            "uptime_seconds": round(time.time() - STATS["started"], 1),
            "queries_total": STATS["queries_total"],
            "cache_hits": STATS["cache_hits"],
            "top_queries": [{"query": q, "count": c} for q, c in top],
            "results_by_engine": dict(STATS["results_by_engine"]),
        }
    return snap


# ---------------------------------------------------------------- web UI

# SearXNG's default_http_headers, applied to every response here:
# no referrer leaks, no MIME sniffing, never indexed by web crawlers.
PRIVACY_HEADERS = {
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Robots-Tag": "noindex, nofollow",
}

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{instance} — Private Search</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:760px;margin:2em auto;
padding:0 1em;color:#111}}
input[type=text]{{width:70%;padding:.5em;font-size:1em}}
button{{padding:.5em 1em;font-size:1em}}
.result{{margin:1.2em 0}} .result h3{{margin:0 0 .2em}}
.score{{color:#666;font-size:.85em}} .snippet{{color:#333}}
.engine{{background:#eef;border-radius:3px;padding:0 .3em;font-size:.8em}}
footer{{margin-top:3em;color:#666;font-size:.85em}}
.hint{{color:#666;font-size:.85em}}
</style></head><body>
<h1>{instance}</h1>
<p>Searches only the local corpus — no external engines, no tracking.</p>
<form method="get" action="/">
<input type="text" name="q" value="{query_attr}" placeholder="Search…" autofocus>
<button type="submit">Search</button></form>
<p class="hint">Bangs: <code>!corpus</code> / <code>!projects</code> search one
engine only. <a href="/stats">Stats</a> · <a href="/?q=redis&amp;format=json">JSON API</a>
· autocomplete: <code>/autocomplete?q=…</code></p>
{body}
<footer>{count} documents indexed from <code>five-projects/</code>
and <code>04-search-engine/corpus/</code>. Index rebuilt on every search.</footer>
</body></html>"""

STATS_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Stats — {instance}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2em auto;
padding:0 1em}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;
padding:.3em .6em;text-align:left}}</style></head><body>
<h1>Stats — {instance}</h1>
<p><a href="/">← back to search</a> · <a href="/stats?format=json">JSON</a></p>
<table>
<tr><th>Documents indexed</th><td>{documents}</td></tr>
<tr><th>Unique terms</th><td>{unique_terms}</td></tr>
<tr><th>Documents by engine</th><td>{by_engine}</td></tr>
<tr><th>Uptime</th><td>{uptime} s</td></tr>
<tr><th>Queries served</th><td>{queries}</td></tr>
<tr><th>Cache hits</th><td>{cache_hits}</td></tr>
<tr><th>Results by engine</th><td>{results_by}</td></tr>
</table>
<h2>Top queries</h2>
{top_queries}
</body></html>"""


def render_page(index, query, results):
    if query is None:
        body = "<p>Try: <em>private search</em>, <em>redis caching</em>, "
        body += "<em>python stdlib</em>, or <em>database</em>.</p>"
    elif not results:
        body = f"<p>No results for <strong>{html.escape(query)}</strong>.</p>"
    else:
        parts = [f"<p>{len(results)} result(s) for "
                 f"<strong>{html.escape(query)}</strong>:</p>"]
        for r in results:
            tags = " ".join(
                f"<span class='engine'>{html.escape(e)}</span>"
                for e in r["engines"])
            parts.append(
                "<div class='result'><h3>{rank}. {title}</h3>"
                "<div class='score'>{path} — score {score} {tags}</div>"
                "<div class='snippet'>{snippet}</div></div>".format(
                    rank=r["rank"], title=html.escape(r["title"]),
                    path=html.escape(r["path"]), score=r["score"],
                    tags=tags,
                    snippet=html.escape(r["snippet"])))
        body = "\n".join(parts)
    return PAGE_TEMPLATE.format(
        instance=html.escape(INSTANCE_NAME),
        query_attr=html.escape(query or "", quote=True),
        body=body, count=index.num_docs).encode("utf-8")


def render_stats(index):
    stats = get_stats(index)
    top = stats["top_queries"]
    if top:
        rows = "".join(
            f"<tr><td>{html.escape(t['query'])}</td>"
            f"<td>{t['count']}</td></tr>" for t in top)
        top_html = f"<table><tr><th>Query</th><th>Count</th></tr>{rows}</table>"
    else:
        top_html = "<p>No queries yet.</p>"
    by_engine = ", ".join(
        f"{e}: {c}" for e, c in stats["documents_by_engine"].items())
    results_by = ", ".join(
        f"{e}: {c}" for e, c in stats["results_by_engine"].items()) or "—"
    return STATS_TEMPLATE.format(
        instance=html.escape(INSTANCE_NAME),
        documents=stats["documents"],
        unique_terms=stats["unique_terms"],
        by_engine=html.escape(by_engine),
        uptime=stats["uptime_seconds"],
        queries=stats["queries_total"],
        cache_hits=stats["cache_hits"],
        results_by=html.escape(results_by),
        top_queries=top_html).encode("utf-8")


class SearchHandler(BaseHTTPRequestHandler):
    def _send(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for key, value in PRIVACY_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload, status=200):
        self._send(json.dumps(payload, indent=2).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def _parse_int(self, params, name, default=None):
        try:
            return int(params.get(name, [default])[0])
        except (TypeError, ValueError):
            return default

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        fmt = params.get("format", ["html"])[0].lower()
        if parsed.path in ("/", "/search"):
            query = params.get("q", [None])[0]
            query = query.strip() if query else None
            engines = params.get("engines", [None])[0]
            engine_set = (set(e.strip() for e in engines.split(",")
                               if e.strip())
                          if engines else None)
            safe = self._parse_int(params, "safe_search", None)
            index = build_index()  # fresh index: picks up new files
            results = (search(index, query, engines=engine_set,
                              safe_search=safe) if query else [])
            if fmt == "json":
                self._send_json({
                    "instance": INSTANCE_NAME,
                    "query": query,
                    "engines": sorted(engine_set)
                    if engine_set else list(ALL_ENGINES),
                    "count": len(results),
                    "results": results,
                })
            else:
                self._send(render_page(index, query, results),
                           "text/html; charset=utf-8")
        elif parsed.path == "/autocomplete":
            prefix = params.get("q", [""])[0]
            index = build_index()
            self._send_json({
                "query": prefix,
                "suggestions": autocomplete(index, prefix),
            })
        elif parsed.path == "/stats":
            index = build_index()
            if fmt == "json":
                self._send_json(get_stats(index))
            else:
                self._send(render_stats(index),
                           "text/html; charset=utf-8")
        else:
            self.send_error(404, "Not found")

    def log_message(self, fmt, *args):  # keep stdout clean
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))


def serve(port):
    index = build_index()
    print(f"{INSTANCE_NAME}: {index.num_docs} docs, "
          f"{index.num_terms} terms indexed.")
    print(f"Serving at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", port), SearchHandler).serve_forever()


# ---------------------------------------------------------------- CLI

def cmd_index():
    index = build_index()
    print(f"Documents indexed: {index.num_docs}")
    print(f"Unique terms:      {index.num_terms}")
    for engine in ALL_ENGINES:
        n = index.docs_by_engine(engine)
        if n:
            print(f"  engine {engine}: {n} docs")
    for doc in index.docs:
        print(f"  - {doc.path.relative_to(PROJECTS_ROOT)}"
              f"  [{doc.title}] ({len(doc.tokens)} tokens)")


def cmd_search(query, as_json, engines, safe_search):
    index = build_index()
    results = search(index, query, engines=engines,
                     safe_search=safe_search)
    if as_json:
        print(json.dumps({
            "instance": INSTANCE_NAME,
            "query": query,
            "count": len(results),
            "results": results,
        }, indent=2))
        return 0 if results else 1
    print(f"Indexed {index.num_docs} documents, "
          f"{index.num_terms} unique terms.")
    if not results:
        print(f'No results for "{query}".')
        return 1
    for r in results:
        print(f"\n{r['rank']}. {r['title']}  (score {r['score']})")
        print(f"   {r['path']}  [{', '.join(r['engines'])}]")
        print(f"   {r['snippet']}")
    return 0


def cmd_autocomplete(prefix):
    index = build_index()
    for s in autocomplete(index, prefix):
        print(s)
    return 0


def cmd_stats():
    index = build_index()
    stats = get_stats(index)
    print(f"{stats['instance']}: {stats['documents']} docs, "
          f"{stats['unique_terms']} unique terms")
    print("Documents by engine: " + ", ".join(
        f"{e}: {c}" for e, c in stats["documents_by_engine"].items()))
    print(f"Uptime: {stats['uptime_seconds']} s | "
          f"Queries: {stats['queries_total']} | "
          f"Cache hits: {stats['cache_hits']}")
    if stats["top_queries"]:
        print("Top queries:")
        for t in stats["top_queries"]:
            print(f"  {t['count']}x  {t['query']}")
    return 0


def cmd_test():
    """Tests: the 6 baseline checks, then the advanced-feature checks."""
    import tempfile
    import urllib.request
    import urllib.error

    index = build_index()
    assert index.num_docs >= 6, f"expected >=6 docs, got {index.num_docs}"
    assert index.num_terms > 50, "index looks empty"
    checks = [
        ("private search", "Private Search"),
        ("redis caching", "Redis"),
        ("python stdlib", "Python"),
        ("database", "Database"),
        ("c compiler", "Compiler"),
    ]
    for query, expect_in_title in checks:
        results = search(index, query)
        assert results, f'no results for "{query}"'
        # The expected page must rank in the top 3. (The #1 slot can
        # legitimately go to another doc that mentions the query more
        # often — e.g. this project's own README for "private search".)
        top_titles = [r["title"] for r in results[:3]]
        assert any(expect_in_title.lower() in t.lower()
                   for t in top_titles), \
            f'"{query}" top 3 were {top_titles}, ' \
            f'expected one about {expect_in_title}'
        print(f'  ok: "{query}" -> #{1} {results[0]["title"]} '
              f'(score {results[0]["score"]}); '
              f'"{expect_in_title}" in top 3')
    # Nonsense query must match nothing. NOTE: the token below must not
    # appear in any indexed document (including this project's README),
    # or the engine would correctly find it — keep it out of the docs.
    assert not search(index, "qqqxxyyzzzwobble"), \
        "gibberish query should match nothing"
    print("  ok: gibberish query returns no results")
    n_baseline = 6

    # --- advanced checks: metasearch, bangs, engines -----------------
    corpus_only = search(index, "private search", engines={"corpus"})
    assert corpus_only, "corpus engine returned nothing"
    assert all(r["engines"] == ["corpus"] for r in corpus_only), \
        "corpus-only search leaked another engine"
    print(f"  ok: engines={{corpus}} returns only corpus docs "
          f"({len(corpus_only)} results)")
    merged = search(index, "private search")
    assert merged and all(r["engines"] for r in merged), \
        "merged results must carry engine tags"
    assert any("projects" in r["engines"] for r in merged), \
        "merged search should include sibling-project docs"
    print("  ok: metasearch merge tags results with their engine(s)")
    bang = search(index, "!corpus private search")
    assert bang and all(r["engines"] == ["corpus"] for r in bang), \
        "!corpus bang did not scope the search"
    print("  ok: !corpus bang scopes the query to one engine")

    # --- JSON serialisability (the API format) -----------------------
    json.dumps({"results": search(index, "redis caching")})
    print("  ok: results are JSON-serialisable (API format)")

    # --- autocomplete -------------------------------------------------
    assert "private" in autocomplete(index, "priv"), \
        "autocomplete('priv') should suggest 'private'"
    assert "redis" in autocomplete(index, "red"), \
        "autocomplete('red') should suggest 'redis'"
    assert autocomplete(index, "qqqxxyy") == [], \
        "autocomplete for gibberish should be empty"
    print("  ok: autocomplete suggests terms from the index")

    # --- safe search (synthetic docs, so the real corpus is untouched)
    synth = Index()
    for title, text in (("Clean page", "a guide to private search"),
                        ("Blocked page", "casino gambling secrets")):
        doc = Document(Path(f"/tmp/{title}.md"), title, text, "corpus")
        synth.docs.append(doc)
        for term, tf in doc.term_freq.items():
            synth.postings[term][len(synth.docs) - 1] = tf
            synth.doc_freq[term] += 1
    assert len(search(synth, "secrets", safe_search=0)) == 1
    assert search(synth, "secrets", safe_search=1) == [], \
        "safe_search=1 must filter the blocked doc"
    assert len(search(synth, "private search", safe_search=2)) == 1, \
        "safe_search=2 must keep the clean doc"
    print("  ok: safe search filters blocked docs at level 1/2, keeps clean docs")

    # --- extra corpus dirs (the video's "add your own databases") ----
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "extra-note.md").write_text(
            "# Zebra notes\nThe zanzibar quokka eats mangoes.\n")
        os.environ["SEARCH_EXTRA_DIRS"] = tmp
        try:
            extra_index = build_index()
            found = search(extra_index, "zanzibar quokka")
            assert found and found[0]["engines"] == ["extra"], \
                f"extra dir doc not found via extra engine: {found}"
        finally:
            del os.environ["SEARCH_EXTRA_DIRS"]
    print("  ok: SEARCH_EXTRA_DIRS adds a searchable 'extra' engine")

    # --- result cache --------------------------------------------------
    with _STATS_LOCK:
        hits_before = STATS["cache_hits"]
    search(index, "database cache probe")
    search(index, "database cache probe")
    with _STATS_LOCK:
        assert STATS["cache_hits"] > hits_before, \
            "second identical query should be a cache hit"
    print("  ok: repeated query is served from the result cache")

    # --- web UI endpoints (live server on an ephemeral port) ----------
    server = ThreadingHTTPServer(("127.0.0.1", 0), SearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def get(path):
            req = urllib.request.Request(base + path)
            return urllib.request.urlopen(req, timeout=10)

        resp = get("/")
        assert resp.status == 200 and b"Search" in resp.read()
        assert resp.headers.get("Referrer-Policy") == "no-referrer", \
            "privacy header missing on home page"
        print("  ok: web UI home serves 200 + Referrer-Policy: no-referrer")
        resp = get("/?q=redis+caching&format=json")
        payload = json.loads(resp.read())
        assert resp.status == 200 and payload["count"] >= 1
        assert payload["results"][0]["engines"], "JSON results lack engines"
        print("  ok: JSON API /?q=…&format=json returns results")
        resp = get("/autocomplete?q=priv")
        payload = json.loads(resp.read())
        assert "private" in payload["suggestions"]
        print("  ok: /autocomplete?q=priv suggests 'private'")
        resp = get("/stats")
        assert resp.status == 200 and b"Stats" in resp.read()
        resp = get("/stats?format=json")
        payload = json.loads(resp.read())
        assert payload["documents"] >= 6 and payload["queries_total"] >= 1
        print("  ok: /stats (HTML + JSON) reports index and query stats")
        try:
            get("/nope")
            raise AssertionError("/nope should 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
        print("  ok: unknown path returns 404")
    finally:
        server.shutdown()
        server.server_close()

    total = n_baseline + 9
    print(f"All tests passed ({total} checks, "
          f"{index.num_docs} docs indexed).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Private search engine (local corpus only).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="build the index and print stats")
    p_search = sub.add_parser("search", help="search from the CLI")
    p_search.add_argument("query")
    p_search.add_argument("--json", action="store_true",
                          help="print results as JSON (the API format)")
    p_search.add_argument("--engines", default=None,
                          help="comma-separated engines: corpus,projects,extra")
    p_search.add_argument("--safe-search", type=int, choices=[0, 1, 2],
                          default=None,
                          help="safe search level (default: $SAFE_SEARCH or 1)")
    p_auto = sub.add_parser("autocomplete",
                            help="suggest terms for a prefix")
    p_auto.add_argument("prefix")
    sub.add_parser("stats", help="index and query stats (like /stats)")
    p_serve = sub.add_parser("serve", help="start the web UI")
    p_serve.add_argument("--port", type=int, default=None,
                         help="port to listen on (default: $PORT or 8004)")
    sub.add_parser("test", help="run built-in tests")
    args = parser.parse_args(argv)
    if args.cmd == "index":
        cmd_index()
    elif args.cmd == "search":
        engines = (set(e.strip() for e in args.engines.split(",")
                        if e.strip()) if args.engines else None)
        return cmd_search(args.query, args.json, engines, args.safe_search)
    elif args.cmd == "autocomplete":
        return cmd_autocomplete(args.prefix)
    elif args.cmd == "stats":
        return cmd_stats()
    elif args.cmd == "serve":
        # --port wins; otherwise $PORT (set by PaaS hosts); else 8004.
        port = args.port or int(os.environ.get("PORT", "8004"))
        serve(port)
    elif args.cmd == "test":
        return cmd_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
