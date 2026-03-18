#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "scripts" / "fpl_creator_watchlist.json"
DEFAULT_OUT = ROOT / "backend" / "data" / "content" / "creator_digest.json"

KEYWORDS = {
    "captain": ["captain", "captaincy"],
    "transfer": ["transfer", "transfers"],
    "wildcard": ["wildcard"],
    "bench_boost": ["bench boost", "benchboost"],
    "triple_captain": ["triple captain"],
    "free_hit": ["free hit", "freehit"],
    "differential": ["differential", "differentials"],
    "deadline": ["deadline"],
}


def _run_ytsearch(query: str, count: int) -> list[dict]:
    search_expr = f"ytsearch{count}:{query}"
    cmd = [
        "yt-dlp",
        search_expr,
        "--skip-download",
        "--dump-json",
        "--no-warnings",
        "--quiet",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return []

    out = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    return out


def _keyword_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for tag, variants in KEYWORDS.items():
        if any(v in lowered for v in variants):
            hits.append(tag)
    return hits


def _tokenize_title(title: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']+", title)
    return [t for t in tokens if len(t) > 2]


def build_digest(videos_per_creator: int = 5) -> dict:
    data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    creators = data.get("creators", [])

    all_items: list[dict] = []
    topic_counter = Counter()
    title_word_counter = Counter()
    by_creator_count = defaultdict(int)

    for c in creators:
        name = c.get("name", "unknown")
        query = c.get("query", name)
        weight = float(c.get("weight", 1.0))
        items = _run_ytsearch(query, videos_per_creator)

        for item in items:
            title = item.get("title") or ""
            description = item.get("description") or ""
            url = item.get("webpage_url") or f"https://www.youtube.com/watch?v={item.get('id')}"
            upload_date = item.get("upload_date")
            channel = item.get("channel") or item.get("uploader") or name

            text_blob = f"{title}\n{description}"
            tags = _keyword_hits(text_blob)
            for t in tags:
                topic_counter[t] += weight

            for tok in _tokenize_title(title):
                title_word_counter[tok.lower()] += weight

            all_items.append(
                {
                    "creator": name,
                    "channel": channel,
                    "title": title,
                    "url": url,
                    "upload_date": upload_date,
                    "duration": item.get("duration"),
                    "view_count": item.get("view_count"),
                    "topics": tags,
                    "weight": weight,
                }
            )
            by_creator_count[name] += 1

    all_items.sort(key=lambda x: (x.get("upload_date") or "", x.get("view_count") or 0), reverse=True)

    top_words = [w for w, _ in title_word_counter.most_common(25) if w not in {"fpl", "fantasy", "premier", "league", "gameweek", "gw"}]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "videos_per_creator": videos_per_creator,
        "creator_coverage": dict(by_creator_count),
        "top_topics": [{"topic": t, "score": round(float(s), 2)} for t, s in topic_counter.most_common(10)],
        "top_title_terms": top_words[:15],
        "videos": all_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FPL creator digest from YouTube search results")
    parser.add_argument("--videos-per-creator", type=int, default=5)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    digest = build_digest(args.videos_per_creator)
    out_path.write_text(json.dumps(digest, indent=2), encoding="utf-8")

    print(f"✅ Creator digest written: {out_path}")
    print(f"   creators covered: {len(digest.get('creator_coverage', {}))}")
    print(f"   videos captured: {len(digest.get('videos', []))}")
    print(f"   top topics: {digest.get('top_topics', [])[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
