# Private Search

A private search engine answers questions from a corpus you control,
without sending your queries to a third party. No tracking cookies, no
search history sold to advertisers, no personalised filter bubble built
from your past searches.

The usual way to get this is SearXNG, a free metasearch engine you can
self-host. SearXNG forwards a query to many public search engines,
merges the results, and strips identifying information before anything
leaves your machine. It never stores your queries.

This project takes a simpler, fully offline approach: instead of
querying the web, it indexes a local corpus of documents on disk and
ranks them with TF-IDF. That makes it private by construction — there
is no network request at all — but it can only answer questions the
corpus already covers. It is a good model of how ranking works, and a
useful tool for searching your own notes and project documentation.

Key ideas: indexing, inverted index, TF-IDF ranking, query parsing,
and result snippets.
