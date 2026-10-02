# VOA inventory (P06)

Counts how many VOA Learning English items are usable as course source text, per level
and per level 4 candidate topic. Metadata only: no article text or audio is kept in the
repo. Output: [`data/voa_inventory.csv`](../../data/voa_inventory.csv) and
[`docs/voa-inventory.md`](../../docs/voa-inventory.md).

```bash
export VOA_CONTACT_EMAIL=you@example.com     # goes into the User-Agent; the crawler refuses without it
make voa-crawl ARGS="--limit 3000"           # resumable; 1 request per second
make voa-report                              # offline: parse the cache, rewrite the CSV and summary
```

## How it behaves

- **Polite.** `robots.txt` is fetched and honoured with its `*` and `$` wildcards
  (`robots.py`; `urllib.robotparser` does not understand them). One request per second,
  an identifying User-Agent with a contact address. Retries count towards the limit.
- **Survives failures.** Timeouts, connection reset or refused, HTTP 429 and 5xx are retried
  (4 attempts, backoff 5, 10, 20 s times a 0.5-1.5 jitter, `Retry-After` honoured; one
  longer than 5 minutes ends the attempts). A URL that still fails, or fails with another
  status such as 403, is written to `index.jsonl` as `{"failed": true, "error": <class>}`
  with no cache file, and the crawl moves on. The next run asks for it again; cached pages
  are still never requested twice. After `--max-consecutive-failures` URLs in a row fail
  (default 20) the run stops with a message and exit code 2: the network or the site is
  down. Every run ends with a summary of fetched, cached, gone, failed and the failure classes.
- **Sitemap, not archive pages.** `robots.txt` disallows the paginated archives, so the
  article list comes from the site's own sitemaps (about 67,000 article URLs).
- **Random order.** URLs are visited in a seeded random order. Any prefix of the crawl is a
  uniform sample, so a partial inventory gives honest counts with a stated coverage.
- **Cache first.** Every response is stored gzip-compressed under `DATA_DIR/voa_cache`
  (default `~/sonari-data`) and never requested twice. The report parses the cache, so a
  change to the parser, licence rules or topic lists needs no new crawl.

## Files

| File | Job |
|---|---|
| `fetch.py`, `robots.py`, `crawl.py` | Polite fetching and the crawl loop |
| `parse.py` | One page to one `Item`: title, programme, date, byline, audio, word count |
| `license.py` | VOA-staff byline, no wire or third-party credit (ADR-0006), conservative |
| `levels.py` | Readability numbers and a coarse level (a sizing heuristic, replaced by P51) |
| `topics.py`, `topics.yaml` | Phrase lists for the eight level 4 topics and replacement candidates; `topics_v1.yaml` is the old keyword baseline |
| `embed.py` | bge-m3 embedding tagger (measured, not used by the report) |
| `sample.py`, `evaluate.py`, `evaluate_render.py` | Labelled sample, tagger scoring, `labels/evaluation.md` |
| `report.py` | CSV plus the Markdown summary |

## Known limits

- Two page templates exist. *Article* pages carry text, a byline (JSON-LD) and usually
  audio. *Media* pages (episodes of *As It Is*, *Learning English Broadcast* and similar)
  carry audio but no text or byline. Media pages are recorded and never counted as usable.
- The byline in the page metadata is always "VOA Learning English", even for AP-sourced
  stories. The licence check therefore also reads the credit line ("reported this story
  for the Associated Press"), body mentions of wire services, and image credits.
- The level is a Flesch-Kincaid band, and topics are keyword tags on title and first
  paragraph. Both are coarse; counts are for sizing, not for choosing passages.
