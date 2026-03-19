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

FPL_CONTEXT_KEYWORDS = [
    "fpl", "fantasy premier league", "gameweek", "gw", "captain", "vice", "transfer", "chip", "wildcard",
    "free hit", "bench boost", "triple captain", "fixture", "xgi", "minutes", "clean sheet", "differential",
    "deadline", "rank", "ownership", "expected points", "xpts", "blank", "double gameweek", "dgw", "bgw",
]

PROMO_PATTERNS = [
    "sponsor", "sponsored", "sponsorship", "paid promotion", "use code", "discount code", "affiliate",
    "affiliate link", "patreon", "join my", "membership", "member", "link in description", "partnered with",
    "thanks to", "brought to you by", "subscribe", "smash the like", "follow me",
]

DRAFT_PATTERNS = [
    "fpl draft", "draft waiver", "waiver tips", "waiver wire", "draft picks", "draft strategy", "draft gw",
]


def _is_promotional(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in PROMO_PATTERNS)


def _is_fpl_relevant(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in FPL_CONTEXT_KEYWORDS)


def _is_draft_centric(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in DRAFT_PATTERNS) or bool(re.search(r"\bdraft\b", low))


def _sentences(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", clean) if len(p.strip()) > 25]


def summarize_text(text: str, max_sentences: int = 6) -> str:
    parts = _sentences(text)
    if not parts:
        return "No detailed summary available yet."

    blacklist = [
        "welcome back", "what is going on everyone", "kind captions language", "captions language",
        "subscribe", "smash the like", "thanks for watching",
    ]

    filtered = []
    for p in parts:
        low = p.lower()
        if any(b in low for b in blacklist):
            continue
        if _is_promotional(low):
            continue
        filtered.append(p)

    if not filtered:
        filtered = [p for p in parts if not _is_promotional(p)]
    if not filtered:
        filtered = parts
    if not filtered:
        return "No detailed summary available yet."

    # Keep summary generic + representative of the whole video by sampling
    # evenly across the transcript instead of templated buckets.
    n = len(filtered)
    k = min(max_sentences, n)
    if k <= 1:
        out = filtered[0]
        return out[:700]

    chosen_idx = []
    for i in range(k):
        idx = round(i * (n - 1) / (k - 1))
        if not chosen_idx or idx != chosen_idx[-1]:
            chosen_idx.append(idx)

    picked = [filtered[i] for i in chosen_idx]
    out = " ".join(picked).strip()
    return out[:700]


def _remove_title(text: str, title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    out = re.sub(r"\s+", " ", (text or "").strip())
    if not out:
        return out
    if t:
        out = re.sub(rf"^{re.escape(t)}[:\-–—\s]*", "", out, flags=re.IGNORECASE).strip()
        out = re.sub(re.escape(t), "", out, flags=re.IGNORECASE).strip()
    out = re.sub(r"\s{2,}", " ", out)
    return out


def _pick_line(parts: list[str], keywords: list[str], fallback: str = "No strong signal.") -> str:
    for s in parts:
        low = s.lower()
        if any(k in low for k in keywords):
            return s
    return fallback


def structured_summary(text: str, *, title: str = "") -> dict:
    parts = _sentences(text)
    parts = [p for p in parts if not _is_promotional(p)]
    fpl_parts = [p for p in parts if _is_fpl_relevant(p)]

    if not fpl_parts:
        fpl_parts = parts

    if not fpl_parts:
        return {
            "key_calls": "No detailed summary available.",
            "buy_watch": "No clear buy signal extracted.",
            "sell_watch": "No clear sell/risk signal extracted.",
            "captain_chips": "No clear captain/chip signal extracted.",
        }

    return {
        "key_calls": _remove_title(_pick_line(fpl_parts, ["overall", "plan", "strategy", "approach", "final thoughts", "key", "gameweek", "transfer", "captain"]), title),
        "buy_watch": _remove_title(_pick_line(fpl_parts, ["buy", "bring", "target", "pick", "consider", "watchlist", "transfer in"]), title),
        "sell_watch": _remove_title(_pick_line(fpl_parts, ["sell", "avoid", "rotation", "injury", "risk", "doubt", "suspended", "minutes", "transfer out"]), title),
        "captain_chips": _remove_title(_pick_line(fpl_parts, ["captain", "vice", "triple captain", "wildcard", "free hit", "bench boost", "chip"]), title),
    }


def decision_oriented_summary(text: str, *, title: str = "") -> str:
    s = structured_summary(text, title=title)

    start_buy = _remove_title(s.get("buy_watch") or "No clear buy/start signal.", title)
    avoid_sell = _remove_title(s.get("sell_watch") or "No clear avoid/sell signal.", title)
    captain_chip = _remove_title(s.get("captain_chips") or "No clear captain/chip signal.", title)

    parts = _sentences(text)
    parts = [p for p in parts if not _is_promotional(p)]
    monitor_line = _pick_line(
        parts,
        ["doubt", "injury", "minutes", "rotation", "press conference", "deadline", "confirmed", "lineup", "team news"],
        fallback="Recheck team news and minutes risk before deadline.",
    )
    monitor_line = _remove_title(monitor_line, title)

    lines = [
        f"Start/Buy: {start_buy}",
        f"Avoid/Sell: {avoid_sell}",
        f"Captain/Chip: {captain_chip}",
        f"Monitor: {monitor_line}",
    ]
    return "\n".join(lines)


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
        title = v.get("title") or ""
        creator = v.get("creator") or ""
        if _is_draft_centric(f"{title} {creator}"):
            continue

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

        # Use youtube-watcher transcript + prior short summary; do not inject title into summary body.
        combined = " ".join([v.get("summary") or "", transcript]).strip()
        s_score = sentiment_score(combined)

        summary_struct = structured_summary(combined, title=title)
        decision_summary = decision_oriented_summary(combined, title=title)
        enriched_videos.append(
            {
                "creator": v.get("creator"),
                "title": title,
                "url": url,
                "video_id": vid,
                "upload_date": v.get("upload_date"),
                "view_count": v.get("view_count"),
                "summary": decision_summary,
                "summary_struct": summary_struct,
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
