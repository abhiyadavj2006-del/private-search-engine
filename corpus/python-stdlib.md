# Python Standard Library

Python ships with a large standard library, so many small tools need no
third-party packages at all. The `http.server` module provides
`BaseHTTPRequestHandler` and `ThreadingHTTPServer`, enough to build a
small local web UI in a single file. The `pathlib` module handles file
paths, `re` handles tokenising text with regular expressions, and
`collections.Counter` counts term frequencies for ranking.

Other useful stdlib pieces: `argparse` for a command-line interface,
`urllib.parse` for reading query strings, `html` for escaping output
so search results cannot inject markup, and `math` for the logarithm
used in TF-IDF scoring.

Because this search engine uses only the standard library, it runs
anywhere Python 3 is installed, with no `pip install` step and no
dependency to break later.
