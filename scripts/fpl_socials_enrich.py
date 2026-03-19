#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIGEST_PATH = ROOT / "backend" / "data" / "content" / "creator_digest.json"
OUT_PATH = ROOT / "backend" / "data" / "content" / "socials_enriched.json"
TRANSCRIPTS_DIR = ROOT / "backend" / "data" / "content" / "transcripts"
WATCHER = Path("/home/openclawuser/.openclaw/workspace/skills/youtube-watcher/scripts/get_transcript.py")

POS_WEIGHTS = {
    "great": 2, "good": 1, "best": 2, "nailed": 2, "essential": 2, "must": 1, "strong": 1, "haul": 2,
    "buy": 1, "start": 1, "captain": 1, "value": 1, "love": 2, "solid": 1, "safe": 1, "upside": 1,
    "form": 1, "improving": 1, "returns": 1, "clean": 1,
}
NEG_WEIGHTS = {
    "bad": 2, "poor": 2, "awful": 3, "bench": 2, "drop": 1, "sell": 2, "avoid": 2, "injury": 3,
    "injured": 3, "rotation": 2, "risk": 2, "doubt": 2, "blank": 2, "trap": 2, "weak": 1,
    "suspended": 3, "minutes": 1, "concern": 2, "uncertain": 2, "out": 1,
}


def summarize_text(text: str, max_sentences: int = 8) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "No detailed summary available yet."

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", clean) if len(p.strip()) > 25]
    blacklist = [
        "welcome back", "what is going on everyone", "kind captions language", "captions language",
        "in this one", "we're going to", "we are going to", "fantasy premier league tips",
    ]
    keyword_pref = ["transfer", "captain", "sell", "buy", "fixtures", "injury", "wildcard", "free hit", "bench boost"]

    filtered = []
    for p in parts:
        low = p.lower()
        if any(b in low for b in blacklist):
            continue
        filtered.append(p)

    ranked = sorted(filtered, key=lambda s: (any(k in s.lower() for k in keyword_pref), len(s)), reverse=True)
    picked = ranked[:max_sentences] if ranked else filtered[:max_sentences]
    if not picked:
        picked = parts[:max_sentences]

    out = " ".join(picked).strip()
    return out[:1200]


def sentiment_score(text: str) -> int:
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    pos = sum(POS_WEIGHTS.get(w, 0) for w in words)
    neg = sum(NEG_WEIGHTS.get(w, 0) for w in words)
    return int(pos - neg)


def sentiment_label(score: int) -> str:
    if score >= 2:
        return "positive"
    if score <= -2:
        return "negative"
    return "neutral"


def extract_video_id(url: str) -> str:
    m = re.search(r"v=([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    return re.sub(r"[^A-Za-z0-9_-]", "", url)[-12:] or "video"


def extract_player_mentions(text: str, player_names: list[str], max_items: int = 12):
    raw = (text or "")
    low = raw.lower()
    out = []
    for name in player_names:
        n = (name or "").strip()
        if len(n) < 3:
            continue

        pattern = re.compile(rf"\b{re.escape(n.lower())}\b")
        matches = list(pattern.finditer(low))
        if not matches:
            continue

        local_scores = []
        for m in matches[:6]:
            a = max(0, m.start() - 80)
            b = min(len(low), m.end() + 80)
            ctx = low[a:b]
            local_scores.append(sentiment_score(ctx))

        score = int(round(sum(local_scores) / max(1, len(local_scores))))
        out.append({"name": n, "sentiment": sentiment_label(score), "score": score})

    # prioritize strongest sentiment magnitude first
    out.sort(key=lambda x: abs(int(x.get("score", 0))), reverse=True)
    return out[:max_items]


def fetch_transcript(url: str) -> str:
    proc = subprocess.run(
        ["python3", str(WATCHER), url],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "transcript fetch failed")
    return proc.stdout.strip()


def main() -> int:
    if not DIGEST_PATH.exists():
        print(f"Missing digest: {DIGEST_PATH}")
        return 1

    payload = json.loads(DIGEST_PATH.read_text(encoding="utf-8"))
    videos = payload.get("videos", [])

    player_names = [x.get("name") for x in payload.get("top_player_mentions", []) if x.get("name")]

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    enriched_videos = []

    for v in videos:
        url = v.get("url")
        if not url:
            continue
        vid = extract_video_id(url)
        transcript_path = TRANSCRIPTS_DIR / f"{vid}.txt"

        transcript = ""
        err = None
        try:
            transcript = fetch_transcript(url)
            transcript_path.write_text(transcript, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if transcript_path.exists():
                transcript = transcript_path.read_text(encoding="utf-8")

        combined = " ".join([v.get("title") or "", v.get("summary") or "", transcript]).strip()
        s_score = sentiment_score(combined)

        enriched_videos.append(
            {
                "creator": v.get("creator"),
                "title": v.get("title"),
                "url": url,
                "video_id": vid,
                "upload_date": v.get("upload_date"),
                "view_count": v.get("view_count"),
                "summary": summarize_text(combined, max_sentences=8),
                "transcript_path": str(transcript_path.relative_to(ROOT)),
                "transcript": transcript,
                "player_mentions": extract_player_mentions(combined, player_names, max_items=12),
                "sentiment": {"label": sentiment_label(s_score), "score": s_score},
                "error": err,
            }
        )

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "videos_count": len(enriched_videos),
        "videos": enriched_videos,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} with {len(enriched_videos)} videos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
