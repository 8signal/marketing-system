#!/usr/bin/env python3
"""Summarize observable LinkedIn posts without inventing missing metrics."""

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result.update(flatten(item, f"{prefix}/{key}" if prefix else str(key)))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(flatten(item, f"{prefix}/{index}"))
        return result
    return {prefix: value}


def read_rows(path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open(encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            payload = payload.get("posts", payload.get("items", payload.get("data")))
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise ValueError("JSON input must be an array of posts or an object with posts/items/data array")
        return [flatten(row) for row in payload]
    if suffix not in (".csv", ".tsv"):
        raise ValueError("Input must be CSV, TSV, or JSON")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t" if suffix == ".tsv" else ",")
        if not reader.fieldnames:
            raise ValueError("Input has no header")
        return list(reader)


def first(row, *names):
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip() != "":
            return value
    return None


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        cleaned = str(value).replace(",", "").strip()
        parsed = int(cleaned)
        return parsed if parsed >= 0 else None
    except ValueError:
        return None


def date(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            stamp = float(value)
            if stamp > 1e12:
                stamp /= 1000
            return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def format_of(row):
    explicit = first(row, "format", "postFormat")
    if explicit:
        return str(explicit).lower()
    keys = [str(k).lower() for k, value in row.items() if value not in (None, "", False, [])]
    for needle, label in (("document", "document"), ("postvideo", "video"),
                          ("video", "video"), ("postimages", "image"),
                          ("image", "image"), ("article", "article")):
        if any(needle in key for key in keys):
            return label
    return "text" if first(row, "content", "text", "postContent") else None


def canonical_url(value):
    if not value:
        return None
    parts = urlsplit(str(value).strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def normalize(row):
    url = canonical_url(first(row, "url", "linkedinUrl", "postUrl", "socialContent/shareUrl"))
    text = first(row, "text", "content", "postContent", "commentary/text")
    metrics = {
        "reactions": number(first(row, "reactions", "engagement/likes", "likes", "numLikes", "reactionsCount")),
        "comments": number(first(row, "comments", "engagement/comments", "numComments", "commentsCount")),
        "reposts": number(first(row, "reposts", "engagement/shares", "shares", "numShares", "repostsCount")),
    }
    return {
        "url": url,
        "published_at": date(first(row, "published_at", "publishedAt", "postedAt", "date", "createdAt")),
        "text": str(text) if text is not None else None,
        "format": format_of(row),
        **metrics,
        "visible_interactions": sum(metrics.values()) if all(v is not None for v in metrics.values()) else None,
    }


def median(values):
    return statistics.median(values) if values else None


def metric_medians(posts):
    """Median of each count over only the posts where that count is visible."""
    summary = {}
    for metric in ("reactions", "comments", "reposts"):
        values = [p[metric] for p in posts if p[metric] is not None]
        summary[metric] = {"posts": len(values), "median": median(values)}
    return summary


def analyze(rows):
    posts, seen = [], set()
    duplicates = 0
    for raw in rows:
        post = normalize(raw)
        if post["url"] and post["url"] in seen:
            duplicates += 1
            continue
        if post["url"]:
            seen.add(post["url"])
        posts.append(post)
    dated = [p["published_at"] for p in posts if p["published_at"]]
    comparable = [p for p in posts if p["visible_interactions"] is not None]
    groups = defaultdict(list)
    for post in comparable:
        groups[post["format"] or "unknown"].append(post["visible_interactions"])
    by_format = {
        name: {"posts": len(values), "median_visible_interactions": median(values)}
        for name, values in sorted(groups.items())
    }
    formats = defaultdict(list)
    for post in posts:
        formats[post["format"] or "unknown"].append(post)
    ranked = sorted(comparable, key=lambda p: p["visible_interactions"], reverse=True)
    caveats = []
    if len(posts) < 30:
        caveats.append("Fewer than 30 observed posts; patterns are directional.")
    if len(comparable) < len(posts):
        caveats.append("Some posts lack at least one interaction component; excluded from total comparisons, not treated as zero. metric_medians uses only the posts where each count is visible.")
    if len(dated) < len(posts):
        caveats.append("Posting frequency and period completeness cannot be established from all posts.")
    caveats.append("Public interactions are not impressions, engagement rate, clicks, leads, or conversions; sampling may be incomplete.")
    return {
        "posts_observed": len(posts), "duplicates_removed": duplicates,
        "coverage": {key: sum(p[key] is not None for p in posts)
                     for key in ("url", "published_at", "text", "format", "reactions", "comments", "reposts", "visible_interactions")},
        "observed_date_range": {"first": min(dated) if dated else None, "last": max(dated) if dated else None},
        "median_visible_interactions": median([p["visible_interactions"] for p in comparable]),
        "by_format": by_format,
        "metric_medians": metric_medians(posts),
        "metric_medians_by_format": {name: {"posts": len(group), **metric_medians(group)}
                                     for name, group in sorted(formats.items())},
        "top_observed_posts": [{"url": p["url"], "published_at": p["published_at"],
                                "visible_interactions": p["visible_interactions"]} for p in ranked[:5]],
        "posts": posts, "caveats": caveats,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="CSV, TSV or JSON export")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON path")
    args = parser.parse_args()
    try:
        result = analyze(read_rows(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        parser.exit(1, f"Analysis failed: {exc}\n")
    print(f"Analyzed {result['posts_observed']} posts; wrote {args.output}")


if __name__ == "__main__":
    main()
