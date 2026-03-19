"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type Mention = { name: string; sentiment: "positive" | "neutral" | "negative"; score: number };

type SocialsResponse = {
  subreddit: string;
  reddit_window: string;
  youtube_creators: {
    generated_at?: string | null;
    top_topics: Array<{ topic: string; score: number }>;
    videos: Array<{
      creator: string;
      title: string;
      url: string;
      upload_date?: string;
      view_count?: number;
      summary?: string;
      summary_struct?: {
        key_calls?: string;
        buy_watch?: string;
        sell_watch?: string;
        captain_chips?: string;
      };
      transcript?: string;
      transcript_path?: string;
      player_mentions: Mention[];
      sentiment: { label: "positive" | "neutral" | "negative"; score: number };
    }>;
  };
  reddit_threads: Array<{
    title: string;
    url?: string | null;
    score: number;
    num_comments: number;
    summary: string;
    player_mentions: Mention[];
    sentiment: { label: "positive" | "neutral" | "negative"; score: number };
  }>;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

function sentimentClass(label: string) {
  if (label === "positive") return "border-emerald-300 text-emerald-200";
  if (label === "negative") return "border-rose-300 text-rose-200";
  return "border-white/30 text-white/80";
}

function splitMentions(mentions: Mention[]) {
  return {
    positive: mentions.filter((m) => m.sentiment === "positive").map((m) => m.name),
    neutral: mentions.filter((m) => m.sentiment === "neutral").map((m) => m.name),
    negative: mentions.filter((m) => m.sentiment === "negative").map((m) => m.name),
  };
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function shortSummary(text?: string, title?: string, maxChars = 420): string {
  let clean = (text || "").replace(/\s+/g, " ").trim();
  if (!clean) return "Summary unavailable.";

  if (title) {
    const t = title.replace(/\s+/g, " ").trim();
    if (t) {
      const titleRegex = new RegExp(`^${escapeRegExp(t)}[:\-–—\s]*`, "i");
      clean = clean.replace(titleRegex, "").trim();
      const anywhereTitleRegex = new RegExp(escapeRegExp(t), "ig");
      clean = clean.replace(anywhereTitleRegex, "").replace(/\s{2,}/g, " ").trim();
    }
  }

  if (!clean) return "Summary unavailable.";
  if (clean.length <= maxChars) return clean;
  return `${clean.slice(0, maxChars).trim()}…`;
}

export default function SocialsPage() {
  const [data, setData] = useState<SocialsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function loadSocials() {
    const payload = await fetchJson<SocialsResponse>("/api/fpl/socials?limit=5&reddit_window=week");
    setData(payload);
    setError(null);
  }

  useEffect(() => {
    loadSocials().catch((e) => setError(e.message || "Failed to load socials"));
  }, []);

  async function refreshSocials() {
    setRefreshing(true);
    setError(null);
    try {
      const res = await fetchJson<{ ok?: boolean; message?: string; error?: string }>("/api/fpl/socials/refresh?videos_per_creator=4", { method: "POST" });
      if (res.ok === false) {
        setError(`${res.message || "Refresh failed"}${res.error ? `: ${res.error}` : ""}`);
        return;
      }
      await loadSocials();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to refresh socials");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h1 className="text-3xl font-black">FPL Socials</h1>
        <button
          onClick={() => void refreshSocials()}
          disabled={refreshing}
          className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60"
        >
          {refreshing ? "Refreshing..." : "Regenerate Summaries"}
        </button>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className="grid md:grid-cols-2 gap-4">
          <div className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-3">YouTube Creators (Top 5 by views + upload date)</h2>
            {data.youtube_creators.videos.length === 0 ? (
              <p className="text-white/70">No creator digest found yet.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {data.youtube_creators.videos.map((v, idx) => (
                  <li key={`${v.url}-${idx}`} className="border border-white/10 rounded-md p-3 bg-black/20">
                    <p className="font-medium text-white/90">{v.creator}</p>
                    <a href={v.url} target="_blank" rel="noreferrer" className="text-cyan-200 hover:underline">
                      {v.title}
                    </a>
                    <div className="mt-2">
                      <span className={`text-[11px] rounded-full px-2 py-0.5 border ${sentimentClass(v.sentiment.label)}`}>
                        Sentiment: {v.sentiment.label.toUpperCase()} ({v.sentiment.score})
                      </span>
                    </div>
                    {v.player_mentions?.length ? (() => {
                      const g = splitMentions(v.player_mentions);
                      return (
                        <div className="mt-2 space-y-1 text-[11px]">
                          <p><span className="text-emerald-200">Positive:</span> {g.positive.slice(0, 6).join(", ") || "—"}</p>
                          <p><span className="text-white/80">Neutral:</span> {g.neutral.slice(0, 6).join(", ") || "—"}</p>
                          <p><span className="text-rose-200">Negative:</span> {g.negative.slice(0, 6).join(", ") || "—"}</p>
                        </div>
                      );
                    })() : null}
                    <p className="text-white/65 mt-1">👁️ {v.view_count ?? 0} • 📅 {v.upload_date || "unknown"}</p>
                    {v.summary_struct ? (
                      <div className="mt-2 space-y-1 text-white/75">
                        <p><span className="text-white/60">Key calls:</span> {shortSummary(v.summary_struct.key_calls, undefined, 220)}</p>
                        <p><span className="text-emerald-200">Buy watch:</span> {shortSummary(v.summary_struct.buy_watch, undefined, 220)}</p>
                        <p><span className="text-rose-200">Sell/risk watch:</span> {shortSummary(v.summary_struct.sell_watch, undefined, 220)}</p>
                        <p><span className="text-cyan-200">Captain/chips:</span> {shortSummary(v.summary_struct.captain_chips, undefined, 220)}</p>
                      </div>
                    ) : (
                      <p className="text-white/75 mt-2">{shortSummary(v.summary, v.title)}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-3">Top 5 Reddit Threads (r/{data.subreddit})</h2>
            <ul className="space-y-3 text-sm">
              {data.reddit_threads.map((t, idx) => (
                <li key={`${t.title}-${idx}`} className="border border-white/10 rounded-md p-3 bg-black/20">
                  {t.url ? (
                    <a href={t.url} target="_blank" rel="noreferrer" className="font-medium text-cyan-200 hover:underline">
                      {idx + 1}. {t.title}
                    </a>
                  ) : (
                    <p className="font-medium">{idx + 1}. {t.title}</p>
                  )}
                  <p className="text-white/65 mt-1">👍 {t.score} • 💬 {t.num_comments}</p>
                  <div className="mt-2">
                    <span className={`text-[11px] rounded-full px-2 py-0.5 border ${sentimentClass(t.sentiment.label)}`}>
                      Sentiment: {t.sentiment.label.toUpperCase()} ({t.sentiment.score})
                    </span>
                  </div>
                  {t.player_mentions?.length ? (() => {
                    const g = splitMentions(t.player_mentions);
                    return (
                      <div className="mt-2 space-y-1 text-[11px]">
                        <p><span className="text-emerald-200">Positive:</span> {g.positive.slice(0, 6).join(", ") || "—"}</p>
                        <p><span className="text-white/80">Neutral:</span> {g.neutral.slice(0, 6).join(", ") || "—"}</p>
                        <p><span className="text-rose-200">Negative:</span> {g.negative.slice(0, 6).join(", ") || "—"}</p>
                      </div>
                    );
                  })() : null}
                  <p className="text-white/80 mt-2">{shortSummary(t.summary, t.title, 360)}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </main>
  );
}
