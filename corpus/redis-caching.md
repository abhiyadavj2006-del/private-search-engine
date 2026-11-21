# Redis Caching

Redis is an in-memory data store often used as a cache in front of a
slower database. A web request first checks the cache: on a cache hit
the answer comes back from memory in under a millisecond, and on a
cache miss the application queries the database and stores the result
in Redis with a time-to-live so the next identical request is fast.

Common Redis data structures are strings, hashes, lists, sets, and
sorted sets. Expiry is set with EXPIRE or by passing an expiry when a
key is written. A typical pattern for search is to cache the rendered
results page for a popular query for a few minutes, so repeated
searches never touch the index at all.

The trade-off is staleness: a cached answer can be out of date until
its time-to-live expires or the key is invalidated. Cache invalidation
— deciding exactly when to throw a cached value away — is famously one
of the hardest problems in software.
