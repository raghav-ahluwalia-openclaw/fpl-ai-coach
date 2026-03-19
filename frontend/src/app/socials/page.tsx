"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchJson } from "@/lib/api";

type Mention = { name: string; sentiment: "positive" | "neutral" | "negative"; score: number };

type SocialsResponse = {
  subreddit: string;
  reddit_window: string;
  youtube_creators: {
    generated_at?: string | null;
    videos: Array<{
      creator: string;
      title: string;
      url: string;
      upload_date?: string;
      view_count?: number;
      summary?: string;
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
  official_news?: {
    generated_at?: string | null;
    source?: string;
    fixture_updates: Array<{
      gw?: number | null;
      fixture: string;
      kickoff_time?: string | null;
      note?: string;
    }>;
    injuries: Array<{
      player: string;
      team?: string;
      status?: string;
      chance_of_playing_next_round?: number | null;
      selected_by_percent?: number;
      news: string;
    }>;
    error?: string;
  };
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

function SentimentPill({ sentiment }: { sentiment: { label: "positive" | "neutral" | "negative"; score: number } }) {
  return (
    <span className={`text-[11px] rounded-full px-2 py-0.5 border ${sentimentClass(sentiment.label)}`}>
      Sentiment: {sentiment.label.toUpperCase()} ({sentiment.score})
    </span>
  );
}

function MentionsBlock({ mentions }: { mentions: Mention[] }) {
  if (!mentions?.length) return null;
  const g = splitMentions(mentions);
  return (
    <div className="mt-2 space-y-1 text-[11px]">
      <p><span className="text-emerald-200">Positive:</span> {g.positive.slice(0, 6).join(", ") || "—"}</p>
      <p><span className="text-white/80">Neutral:</span> {g.neutral.slice(0, 6).join(", ") || "—"}</p>
      <p><span className="text-rose-200">Negative:</span> {g.negative.slice(0, 6).join(", ") || "—"}</p>
    </div>
  );
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function formatTimestampWithTimezone(raw?: string | null): string {
  if (!raw) return "Unknown";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;

  const fmt = new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
  return fmt.format(d);
}

function shortSummary(text?: string, title?: string): string {
  let clean = (text || "")
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join("\n");
  if (!clean) return "Summary unavailable.";

  if (title) {
    const t = title.replace(/\s+/g, " ").trim();
    if (t) {
      const titleRegex = new RegExp(`^${escapeRegExp(t)}[:\-–—\s]*`, "i");
      clean = clean.replace(titleRegex, "").trim();
      const anywhereTitleRegex = new RegExp(escapeRegExp(t), "ig");
      clean = clean
        .replace(anywhereTitleRegex, "")
        .split("\n")
        .map((line) => line.replace(/\s{2,}/g, " ").trim())
        .filter(Boolean)
        .join("\n");
    }
  }

  if (!clean) return "Summary unavailable.";
  return clean;
}

type InjuryItem = NonNullable<SocialsResponse["official_news"]>["injuries"][number];
type FixtureUpdateItem = NonNullable<SocialsResponse["official_news"]>["fixture_updates"][number];

function OfficialInjuriesCard({ injuries }: { injuries: InjuryItem[] }) {
  return (
    <div className="border border-white/10 rounded-md p-3 bg-black/20">
      <p className="font-medium text-white/90 mb-2">🩺 Player Injury / Availability Flags</p>
      {injuries.length === 0 ? (
        <p className="text-white/70">No major official flags right now.</p>
      ) : (
        <ul className="space-y-2">
          {injuries.slice(0, 10).map((n, idx) => (
            <li key={`${n.player}-${idx}`} className="text-white/80">
              <p>
                <span className="text-white/95 font-medium">{n.player}</span>
                {n.team ? ` (${n.team})` : ""}
                {typeof n.selected_by_percent === "number" ? ` • owned: ${n.selected_by_percent.toFixed(1)}%` : ""}
                {n.status ? ` • status: ${String(n.status).toUpperCase()}` : ""}
                {typeof n.chance_of_playing_next_round === "number" ? ` • chance: ${n.chance_of_playing_next_round}%` : ""}
              </p>
              <p className="text-white/65">{n.news}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OfficialFixtureUpdatesCard({ fixtureUpdates }: { fixtureUpdates: FixtureUpdateItem[] }) {
  return (
    <div className="border border-white/10 rounded-md p-3 bg-black/20">
      <p className="font-medium text-white/90 mb-2">📅 Fixture Rescheduling Signals</p>
      {fixtureUpdates.length === 0 ? (
        <p className="text-white/70">No provisional kickoff updates currently flagged.</p>
      ) : (
        <ul className="space-y-2">
          {fixtureUpdates.map((f, idx) => (
            <li key={`${f.fixture}-${idx}`} className="text-white/80">
              <p className="text-white/95 font-medium">GW{f.gw ?? "?"} • {f.fixture}</p>
              <p className="text-white/65">
                {f.kickoff_time ? new Date(f.kickoff_time).toLocaleString() : "Kickoff TBC"}
                {f.note ? ` • ${f.note}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SocialsPage() {
  const [data, setData] = useState<SocialsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSocials = useCallback(async () => {
    const payload = await fetchJson<SocialsResponse>("/api/fpl/socials?limit=5&reddit_window=week");
    setData(payload);
    setError(null);
    return payload;
  }, []);

  const refreshSocials = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    setRefreshing(true);
    setError(null);
    try {
      const res = await fetchJson<{ ok?: boolean; message?: string; error?: string }>("/api/fpl/socials/refresh?videos_per_creator=4", { method: "POST" });
      if (res.ok === false) {
        setError(`${res.message || "Refresh failed"}${res.error ? `: ${res.error}` : ""}`);
        return;
      }
      await fetchSocials();
    } catch (e: unknown) {
      if (!silent) {
        setError(e instanceof Error ? e.message : "Failed to refresh socials");
      }
    } finally {
      setRefreshing(false);
    }
  }, [fetchSocials]);

  const loadSocials = useCallback(async (opts?: { autoRefreshIfStale?: boolean }) => {
    const payload = await fetchSocials();

    const autoRefreshIfStale = opts?.autoRefreshIfStale ?? false;
    if (!autoRefreshIfStale) return;

    const generatedAt = payload.youtube_creators.generated_at;
    if (!generatedAt) return;

    const generatedMs = Date.parse(generatedAt);
    if (Number.isNaN(generatedMs)) return;

    const ONE_DAY_MS = 24 * 60 * 60 * 1000;
    const stale = Date.now() - generatedMs >= ONE_DAY_MS;
    if (!stale) return;

    await refreshSocials({ silent: true });
  }, [fetchSocials, refreshSocials]);

  useEffect(() => {
    loadSocials({ autoRefreshIfStale: true }).catch((e) => setError(e.message || "Failed to load socials"));
  }, [loadSocials]);

  const refreshedLabel = useMemo(
    () => formatTimestampWithTimezone(data?.youtube_creators?.generated_at),
    [data?.youtube_creators?.generated_at],
  );

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-black">FPL Socials</h1>
          <p className="text-xs text-white/65 mt-1">Last refreshed: {refreshedLabel}</p>
        </div>
        <button
          onClick={() => void refreshSocials()}
          disabled={refreshing}
          className="h-8 w-8 grid place-items-center rounded-full border border-white/30 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition disabled:opacity-60"
          aria-label="Refresh socials"
          title={refreshing ? "Refreshing..." : "Refresh"}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}>
            <path
              d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <>
          <section className="grid md:grid-cols-2 gap-4">
            <div className={cardClass}>
              <h2 className="font-semibold text-[#00ff87] mb-3">YouTube Creators (Top 5 by latest upload date, then views)</h2>
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
                        <SentimentPill sentiment={v.sentiment} />
                      </div>
                      <MentionsBlock mentions={v.player_mentions} />
                      <p className="text-white/65 mt-1">👁️ {v.view_count ?? 0} • 📅 {v.upload_date || "unknown"}</p>
                      <p className="text-white/75 mt-2 whitespace-pre-line">{shortSummary(v.summary, v.title)}</p>
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
                      <SentimentPill sentiment={t.sentiment} />
                    </div>
                    <MentionsBlock mentions={t.player_mentions} />
                    <p className="text-white/80 mt-2">{shortSummary(t.summary, t.title)}</p>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section className="mt-4">
            <div className={cardClass}>
              <h2 className="font-semibold text-[#00ff87] mb-1">Official Premier League Updates</h2>
              <p className="text-xs text-white/60 mb-3">
                Source: {data.official_news?.source || "Official FPL API"}
                {data.official_news?.generated_at ? ` • Updated: ${formatTimestampWithTimezone(data.official_news.generated_at)}` : ""}
              </p>

              {data.official_news?.error ? (
                <p className="text-red-300 text-sm">Could not load official updates: {data.official_news.error}</p>
              ) : (
                <div className="grid md:grid-cols-2 gap-3 text-sm">
                  <OfficialInjuriesCard injuries={data.official_news?.injuries || []} />
                  <OfficialFixtureUpdatesCard fixtureUpdates={data.official_news?.fixture_updates || []} />
                </div>
              )}
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
