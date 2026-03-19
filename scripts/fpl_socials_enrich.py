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

POS_WORDS = {
    "great", "good", "best", "nailed", "essential", "must", "strong", "haul", "buy", "start", "captain", "value", "love", "solid", "safe", "upside", "form"
}
NEG_WORDS = {
    "bad", "poor", "awful", "bench", "drop", "sell", "avoid", "injury", "injured", "rotation", "risk", "doubt", "blank", "trap", "weak"
}


def summarize_text(text: str, max_sentences: int = 8) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "No detailed summary available yet."
    parts = re.split(r"(?<=[.!?])\s+", clean)
    parts = [p.strip() for p in parts if len(p.strip()) > 30]
    return " ".join(parts[:max_sentences]) if parts else clean[:1200]


def sentiment_score(text: str) -> int:
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    pos = sum(1 for w in words if w in POS_WORDS)
    neg = sum(1 for w in words if w in NEG_WORDS)
    return pos - neg


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
    low = (text or "").lower()
    out = []
    for name in player_names:
        n = (name or "").strip()
        if len(n) < 3:
            continue
        if re.search(rf"\b{re.escape(n.lower())}\b", low):
            score = sentiment_score(low)
            out.append({"name": n, "sentiment": sentiment_label(score), "score": score})
        if len(out) >= max_items:
            break
    return out


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
