# Input and normalization

Accept UTF-8 JSON arrays, or objects with a `posts`, `items`, or `data` array; UTF-8 CSV/TSV with headers; and UTF-8 BOM exports. The script reads nested JSON and slash-key columns. No third-party package is required.

Preferred fields per post: `url`, `published_at`, `text`, `format`, `reactions`, `comments`, `reposts`. Common aliases include `linkedinUrl`, `postUrl`, `content`, `postContent`, `engagement/likes`, `engagement/comments`, and `engagement/shares`. Publication dates should be ISO 8601 or Unix seconds/milliseconds. The script does not infer dates from LinkedIn activity IDs.

All interaction components must be present for `visible_interactions` to be computed. A genuine numeric zero remains zero; an absent or invalid count becomes null. The output includes normalized posts, metric coverage, deduplication count, observed date range, median and format breakdown. `metric_medians` and `metric_medians_by_format` give the median of each count over only the posts where that count is visible, with that number of posts (`metric_medians_by_format` also gives each format's total posts); public post pages often show reactions and comments but not reposts, so `visible_interactions` can be null for every post. Duplicates are identified by canonical URL; posts without a valid URL cannot be deduplicated reliably.

The export is a snapshot. Record its provider, acquisition date, search window and collection limit separately in the audit. A profile URL alone is not a structured export. Never imply that a partial sample covers the full account history.
