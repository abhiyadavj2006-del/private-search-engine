# Databases and SQL

A database stores structured data durably and lets you ask questions
about it with a query language. Relational databases such as SQLite
and PostgreSQL organise data into tables with rows and columns, and
SQL is the language for selecting, joining, and aggregating those
rows. An index on a column makes lookups fast, at the cost of slower
writes and extra storage.

For a search engine, the classic database feature is full-text search:
PostgreSQL has `tsvector` and SQLite has the FTS5 extension, both of
which build an inverted index inside the database itself. That is the
same data structure this project builds in memory, but persistent and
maintained by the database as documents change.

Choose SQLite for a single-file local database, and PostgreSQL when
many users write at the same time. A search index and a database solve
different problems: the database is the source of truth, the index is
a fast way to find things in it.
