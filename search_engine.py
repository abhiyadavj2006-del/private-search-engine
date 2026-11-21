#!/usr/bin/env python3
"""
Private search engine — Project 4 of 5.

Searches ONLY a local corpus. No external search engines, no network
calls, no API keys, no tracking. Python standard library only.

Corpus (indexed fresh on every search / server start, so files added
later are picked up automatically):
  1. corpus/  — sample pages shipped with this project, and
  2. ~/workspace/five-projects/ — every README / doc in the sibling
     projects (01-redis, 02-database, 03-ai-agent, 05-c-compiler, ...),
     whatever exists at search time.

Usage:
    python3 search_engine.py index                  # print index stats
    python3 search_engine.py search "private search"
    python3 search_engine.py serve [--port 8004]    # web UI on localhost
    python3 search_engine.py test                   # built-in smoke tests

The server port comes from --port, or from the PORT environment
variable when --port is not given (default 8004). This is what hosts
like Render / Railway / Fly.io set, so the same single command works
locally and when deployed:
    PORT=8004 python3 search_engine.py serve

Ranking: TF-IDF over stemmed-ish tokens, with a x3 boost for terms in
the document title (first heading / first line) and a bonus for an
exact-phrase match.
"""

import argparse
import html
import math
import os
import re
import sys
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

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "this", "to", "was", "were", "will", "with", "you", "your",
    "can", "not", "but", "if", "so", "we", "they", "them", "he", "she",
    "his", "her", "our", "their", "all", "any", "do", "does", "did",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
HTML_TAG_RE = re.compile(r"<[^>]+>")


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
    def __init__(self, path, title, text):
        self.path = path
        self.title = title
        self.text = text  # plain text, for snippets / phrase matching
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


def collect_files():
    """All indexable files under corpus/ and the five-projects tree."""
    roots = [CORPUS_DIR, PROJECTS_ROOT]
    seen = set()
    files = []
    for root in roots:
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
                files.append(p)
    return sorted(files)


def build_index():
    """(Re)build the whole index from disk. Corpus is small, so a full
    rebuild on every search keeps results correct when sibling
    projects add READMEs later — no stale-index problem."""
    index = Index()
    for path in collect_files():
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        text = strip_markup(raw, path.suffix.lower())
        title = extract_title(raw, path)
        doc = Document(path, title, text)
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


def search(index, query, top_n=10):
    """Ranked search. Returns list of dicts: rank, title, path, score,
    snippet. Empty list when nothing matches."""
    query_terms = tokenize(query)
    if not query_terms:
        return []
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
            tf_norm = 1 + math.log(tf) if tf > 0 else 0
            score = tf_norm * idf
            if term in doc.title_tokens:
                score *= 3.0  # title boost
            scores[doc_id] += score
    # Exact-phrase bonus: the whole query appearing verbatim.
    phrase = query.strip().lower()
    if len(query_terms) > 1:
        for doc_id, doc in enumerate(index.docs):
            if phrase in doc.text.lower():
                scores[doc_id] += 2.0
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    results = []
    for rank, (doc_id, score) in enumerate(ranked[:top_n], start=1):
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
        })
    return results


# ---------------------------------------------------------------- web UI

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Private Search</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:760px;margin:2em auto;
padding:0 1em;color:#111}}
input[type=text]{{width:70%;padding:.5em;font-size:1em}}
button{{padding:.5em 1em;font-size:1em}}
.result{{margin:1.2em 0}} .result h3{{margin:0 0 .2em}}
.score{{color:#666;font-size:.85em}} .snippet{{color:#333}}
footer{{margin-top:3em;color:#666;font-size:.85em}}
</style></head><body>
<h1>Private Search</h1>
<p>Searches only the local corpus — no external engines, no tracking.</p>
<form method="get" action="/">
<input type="text" name="q" value="{query_attr}" placeholder="Search…" autofocus>
<button type="submit">Search</button></form>
{body}
<footer>{count} documents indexed from <code>five-projects/</code>
and <code>04-search-engine/corpus/</code>. Index rebuilt on every search.</footer>
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
            parts.append(
                "<div class='result'><h3>{rank}. {title}</h3>"
                "<div class='score'>{path} — score {score}</div>"
                "<div class='snippet'>{snippet}</div></div>".format(
                    rank=r["rank"], title=html.escape(r["title"]),
                    path=html.escape(r["path"]), score=r["score"],
                    snippet=html.escape(r["snippet"])))
        body = "\n".join(parts)
    return PAGE_TEMPLATE.format(
        query_attr=html.escape(query or "", quote=True),
        body=body, count=index.num_docs).encode("utf-8")


class SearchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/", "/search"):
            self.send_error(404, "Not found")
            return
        query = parse_qs(parsed.query).get("q", [None])[0]
        query = query.strip() if query else None
        index = build_index()  # fresh index per request: picks up new files
        results = search(index, query) if query else []
        page = render_page(index, query, results)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, fmt, *args):  # keep stdout clean
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))


def serve(port):
    index = build_index()
    print(f"Private search: {index.num_docs} docs, "
          f"{index.num_terms} terms indexed.")
    print(f"Serving at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", port), SearchHandler).serve_forever()


# ---------------------------------------------------------------- CLI

def cmd_index():
    index = build_index()
    print(f"Documents indexed: {index.num_docs}")
    print(f"Unique terms:      {index.num_terms}")
    for doc in index.docs:
        print(f"  - {doc.path.relative_to(PROJECTS_ROOT)}"
              f"  [{doc.title}] ({len(doc.tokens)} tokens)")


def cmd_search(query):
    index = build_index()
    print(f"Indexed {index.num_docs} documents, "
          f"{index.num_terms} unique terms.")
    results = search(index, query)
    if not results:
        print(f'No results for "{query}".')
        return 1
    for r in results:
        print(f"\n{r['rank']}. {r['title']}  (score {r['score']})")
        print(f"   {r['path']}")
        print(f"   {r['snippet']}")
    return 0


def cmd_test():
    """Smoke tests: indexing + ranking on known corpus content."""
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
    print(f"All smoke tests passed ({index.num_docs} docs indexed).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Private search engine (local corpus only).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="build the index and print stats")
    p_search = sub.add_parser("search", help="search from the CLI")
    p_search.add_argument("query")
    p_serve = sub.add_parser("serve", help="start the web UI")
    p_serve.add_argument("--port", type=int, default=None,
                         help="port to listen on (default: $PORT or 8004)")
    sub.add_parser("test", help="run built-in smoke tests")
    args = parser.parse_args(argv)
    if args.cmd == "index":
        cmd_index()
    elif args.cmd == "search":
        return cmd_search(args.query)
    elif args.cmd == "serve":
        # --port wins; otherwise $PORT (set by PaaS hosts); else 8004.
        port = args.port or int(os.environ.get("PORT", "8004"))
        serve(port)
    elif args.cmd == "test":
        return cmd_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
