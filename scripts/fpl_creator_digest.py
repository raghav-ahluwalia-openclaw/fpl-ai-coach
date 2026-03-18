#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "scripts" / "fpl_creator_watchlist.json"
DEFAULT_OUT = ROOT / "backend" / "data" / "content" / "creator_digest.json"

KEYWORDS = {
    "captain": ["captain", "captaincy", "vice-captain", "vice captain"],
    "transfer": ["transfer", "transfers", "sell", "buy"],
    "wildcard": ["wildcard", "wc"],
    "bench_boost": ["bench boost", "benchboost", "bb chip"],
    "triple_captain": ["triple captain", "tc chip"],
    "free_hit": ["free hit", "freehit", "fh chip"],
    "differential": ["differential", "differentials"],
    "deadline": ["deadline", "lock", "before deadline"],
    "injury": ["injury", "injured", "fitness", "doubt", "flagged"],
    "fixtures": ["fixture", "fixtures", "run of games", "swing"],
}

PLAYER_DB_PATH = ROOT / "backend" / "fpl.db"


def _yt_dlp_json(args: list[str]) -> dict[str, Any] | None:
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except Exception:  # noqa: BLE001
        return None


def _run_ytsearch(query: str, count: int) -> list[dict[str, Any]]:
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

    out: list[dict[str, Any]] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    return out


def _fetch_video_info(url: str) -> dict[str, Any] | None:
    return _yt_dlp_json([
        "yt-dlp",
        url,
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        "--quiet",
    ])


def _lang_candidates(captions: dict[str, Any]) -> list[str]:
    preferred = ["en", "en-US", "en-GB", "en-CA"]
    keys = list(captions.keys())
    out = [k for k in preferred if k in captions]
    out.extend([k for k in keys if k.startswith("en") and k not in out])
    return out


def _pick_caption_url(info: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not info:
        return None, None

    for source_key in ["subtitles", "automatic_captions"]:
        source = info.get(source_key)
        if not isinstance(source, dict):
            continue
        langs = _lang_candidates(source)
        for lang in langs:
            formats = source.get(lang) or []
            if not isinstance(formats, list):
                continue

            # prefer easier-to-parse formats first
            preferred_ext = ["vtt", "json3", "srv3", "ttml"]
            formats_sorted = sorted(
                [f for f in formats if isinstance(f, dict) and f.get("url")],
                key=lambda f: preferred_ext.index(f.get("ext")) if f.get("ext") in preferred_ext else 99,
            )
            for f in formats_sorted:
                return str(f.get("url")), str(f.get("ext") or "")
    return None, None


def _fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-ai-coach/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_html_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_player_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    if not PLAYER_DB_PATH.exists():
        return aliases

    try:
        conn = sqlite3.connect(PLAYER_DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT first_name, second_name, web_name FROM players")
        for first_name, second_name, web_name in cur.fetchall():
            first_name = (first_name or "").strip()
            second_name = (second_name or "").strip()
            web_name = (web_name or "").strip()
            canonical = web_name or second_name or (f"{first_name} {second_name}".strip())
            if not canonical:
                continue

            candidate_aliases = {
                web_name,
                second_name,
                f"{first_name} {second_name}".strip(),
            }
            for alias in candidate_aliases:
                alias_n = _normalize_text(alias)
                if len(alias_n) < 3:
                    continue
                aliases[alias_n] = canonical
        conn.close()
    except Exception:  # noqa: BLE001
        return {}

    return aliases


def _player_mentions(text: str, alias_map: dict[str, str], max_items: int = 8) -> list[dict[str, Any]]:
    if not text or not alias_map:
        return []
    txt = f" {_normalize_text(text)} "

    counts: Counter[str] = Counter()
    for alias_norm, canonical in alias_map.items():
        if len(alias_norm) < 3:
            continue
        # phrase boundary by spaces after normalization
        needle = f" {alias_norm} "
        c = txt.count(needle)
        if c > 0:
            counts[canonical] += c

    out = [{"name": name, "mentions": int(cnt)} for name, cnt in counts.most_common(max_items)]
    return out


def _parse_vtt(raw: str) -> str:
    lines: list[str] = []
    prev = ""
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if s.upper().startswith("WEBVTT"):
            continue
        if "-->" in s:
            continue
        if re.match(r"^\d+$", s):
            continue
        if low.startswith(("kind:", "language:", "align:", "position:", "line:", "size:")):
            continue
        cleaned = _strip_html_tags(s)
        if not cleaned:
            continue
        if cleaned == prev:
            continue
        lines.append(cleaned)
        prev = cleaned
    return " ".join(lines).strip()


def _parse_json3(raw: str) -> str:
    try:
        obj = json.loads(raw)
    except Exception:  # noqa: BLE001
        return ""
    events = obj.get("events") if isinstance(obj, dict) else None
    if not isinstance(events, list):
        return ""
    out = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        segs = ev.get("segs")
        if not isinstance(segs, list):
            continue
        for seg in segs:
            if isinstance(seg, dict):
                txt = seg.get("utf8")
                if isinstance(txt, str):
                    out.append(txt)
    return _strip_html_tags(" ".join(out))


def _transcript_text(video_info: dict[str, Any] | None) -> str:
    url, ext = _pick_caption_url(video_info)
    if not url:
        return ""
    try:
        raw = _fetch_text(url)
    except Exception:  # noqa: BLE001
        return ""

    ext = (ext or "").lower()
    if ext in {"json3", "srv3"}:
        txt = _parse_json3(raw)
        if txt:
            return txt
    if ext in {"vtt", "ttml", "srv1", "srv2"}:
        txt = _parse_vtt(raw)
        if txt:
            return txt

    # fallback generic cleanup
    return _strip_html_tags(raw)


def _keyword_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for tag, variants in KEYWORDS.items():
        if any(v in lowered for v in variants):
            hits.append(tag)
    return sorted(set(hits))


def _tokenize_title(title: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']+", title)
    return [t for t in tokens if len(t) > 2]


def _summarize(transcript: str, title: str, max_len: int = 320) -> str:
    if not transcript:
        return f"{title} (transcript unavailable; summary based on title only)."

    # quick extractive summary: first coherent 2-3 sentences
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript) if len(s.strip()) > 25]
    if not sents:
        trimmed = transcript[: max_len - 3].strip()
        return trimmed + ("..." if len(transcript) > len(trimmed) else "")

    picked = []
    total = 0
    for s in sents:
        if total + len(s) > max_len and picked:
            break
        picked.append(s)
        total += len(s) + 1
        if len(picked) >= 3:
            break

    out = " ".join(picked).strip()
    if len(out) > max_len:
        out = out[: max_len - 3].rstrip() + "..."
    return out


def build_digest(videos_per_creator: int = 5) -> dict[str, Any]:
    data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    creators = data.get("creators", [])

    all_items: list[dict[str, Any]] = []
    topic_counter: Counter[str] = Counter()
    title_word_counter: Counter[str] = Counter()
    player_counter: Counter[str] = Counter()
    by_creator_count: dict[str, int] = defaultdict(int)

    info_cache: dict[str, dict[str, Any] | None] = {}
    alias_map = _load_player_aliases()

    for c in creators:
        name = c.get("name", "unknown")
        query = c.get("query", name)
        weight = float(c.get("weight", 1.0))
        items = _run_ytsearch(query, videos_per_creator)

        for item in items:
            title = item.get("title") or ""
            description = item.get("description") or ""
            vid = item.get("id")
            url = item.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
            upload_date = item.get("upload_date")
            channel = item.get("channel") or item.get("uploader") or name

            if not url:
                continue

            if url not in info_cache:
                info_cache[url] = _fetch_video_info(url)
            info = info_cache[url]

            transcript = _transcript_text(info)
            summary = _summarize(transcript, title)

            blob = "\n".join([title, description, transcript])
            tags = _keyword_hits(blob)
            for t in tags:
                topic_counter[t] += weight

            player_mentions = _player_mentions(blob, alias_map, max_items=8)
            for pm in player_mentions:
                player_counter[pm["name"]] += float(pm["mentions"]) * weight

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
                    "transcript_tags": tags,
                    "player_mentions": player_mentions,
                    "transcript_available": bool(transcript),
                    "summary": summary,
                    "weight": weight,
                }
            )
            by_creator_count[name] += 1

    all_items.sort(key=lambda x: (x.get("upload_date") or "", x.get("view_count") or 0), reverse=True)

    top_words = [
        w
        for w, _ in title_word_counter.most_common(25)
        if w not in {"fpl", "fantasy", "premier", "league", "gameweek", "gw"}
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "videos_per_creator": videos_per_creator,
        "creator_coverage": dict(by_creator_count),
        "top_topics": [{"topic": t, "score": round(float(s), 2)} for t, s in topic_counter.most_common(10)],
        "top_title_terms": top_words[:15],
        "top_player_mentions": [
            {"name": name, "score": round(float(score), 2)}
            for name, score in player_counter.most_common(20)
        ],
        "videos": all_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FPL creator digest from YouTube search + transcript summaries")
    parser.add_argument("--videos-per-creator", type=int, default=5)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    digest = build_digest(args.videos_per_creator)
    out_path.write_text(json.dumps(digest, indent=2), encoding="utf-8")

    transcript_count = sum(1 for v in digest.get("videos", []) if v.get("transcript_available"))

    print(f"✅ Creator digest written: {out_path}")
    print(f"   creators covered: {len(digest.get('creator_coverage', {}))}")
    print(f"   videos captured: {len(digest.get('videos', []))}")
    print(f"   transcripts found: {transcript_count}")
    print(f"   top topics: {digest.get('top_topics', [])[:5]}")
    print(f"   top player mentions: {digest.get('top_player_mentions', [])[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
