"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchJson } from "@/lib/api";

type AppSettings = { fpl_entry_id: number | null };

type LeagueRow = {
  league_id: number;
  name: string;
  type: "classic" | "h2h" | string;
  entry_count: number;
  your_rank: number;
  last_rank: number;
  rank_delta: number;
  you_points: number;
  leader_points: number;
  gap_to_leader: number;
  gap_to_next_above?: number | null;
  gap_to_next_below?: number | null;
  percentile: number;
  last_updated_data?: string | null;
  around: Array<{
    rank: number;
    entry: number;
    entry_name?: string;
    manager?: string;
    points: number;
    event_points: number;
  }>;
};

type LeaguesResponse = {
  entry_id: number;
  generated_at: string;
  summary: {
    league_count: number;
    classic_count: number;
    h2h_count: number;
  };
  insights: Array<{ type: string; text: string }>;
  leagues: LeagueRow[];
};

type RankPoint = {
  event: number;
  overall_rank: number;
  event_points: number;
  total_points: number;
};

type RankHistoryResponse = {
  entry_id: number;
  points: RankPoint[];
  best_rank?: number;
  worst_rank?: number;
  summary: string;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

function formatNum(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString();
}

function rankDeltaClass(delta: number): string {
  if (delta > 0) return "text-emerald-300";
  if (delta < 0) return "text-rose-300";
  return "text-white/70";
}

function rankDeltaLabel(delta: number): string {
  return delta > 0 ? `+${formatNum(delta)}` : formatNum(delta);
}

function percentileOrH2h(row: LeagueRow): string {
  return row.type === "h2h" ? formatNum(row.you_points) : `${row.percentile.toFixed(1)}%`;
}

function percentileLabelForRow(row: LeagueRow): string {
  return row.type === "h2h" ? "H2H Pts" : "Percentile";
}

function formatInsightText(text: string): string {
  return text.replace(/([+-]?\d{4,})/g, (m) => {
    const n = Number(m);
    if (!Number.isFinite(n)) return m;
    return n.toLocaleString();
  });
}

function formatRank(n: number | undefined) {
  if (!n) return "-";
  return n.toLocaleString();
}

function formatDelta(delta: number | null): string {
  if (delta === null) return "-";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toLocaleString()}`;
}

export default function LeaguesPage() {
  const [teamId, setTeamId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LeaguesResponse | null>(null);
  const [rankData, setRankData] = useState<RankHistoryResponse | null>(null);
  const [rankError, setRankError] = useState<string | null>(null);
  const [leagueFilter, setLeagueFilter] = useState<"all" | "classic" | "h2h">("all");
  const hasAutoRun = useRef(false);

  useEffect(() => {
    fetchJson<AppSettings>("/api/fpl/settings")
      .then((s) => {
        if (s.fpl_entry_id) setTeamId(String(s.fpl_entry_id));
      })
      .catch(() => null);
  }, []);

  const run = useCallback(async (idOverride?: string) => {
    const id = (idOverride ?? teamId).trim();
    if (!/^\d+$/.test(id)) {
      setError("Team ID must be numeric.");
      return;
    }

    setLoading(true);
    setError(null);
    setRankError(null);
    try {
      const [leaguesRes, rankRes] = await Promise.allSettled([
        fetchJson<LeaguesResponse>(`/api/fpl/team/${id}/leagues`),
        fetchJson<RankHistoryResponse>(`/api/fpl/team/${id}/rank-history`),
      ]);

      if (leaguesRes.status === "fulfilled") {
        setData(leaguesRes.value);
      } else {
        throw leaguesRes.reason;
      }

      if (rankRes.status === "fulfilled") {
        setRankData(rankRes.value);
      } else {
        setRankData(null);
        setRankError(rankRes.reason instanceof Error ? rankRes.reason.message : "Failed to load rank trend");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load leagues.");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    if (!hasAutoRun.current && /^\d+$/.test(teamId.trim())) {
      hasAutoRun.current = true;
      void run(teamId.trim());
    }
  }, [teamId, run]);

  const classicPts = data?.leagues.find((l) => l.type === "classic" && l.name === "Overall")?.you_points
    ?? data?.leagues.find((l) => l.type === "classic")?.you_points;

  const visibleLeagues = useMemo(() => {
    if (!data) return [] as LeagueRow[];
    if (leagueFilter === "all") return data.leagues;
    return data.leagues.filter((l) => l.type === leagueFilter);
  }, [data, leagueFilter]);

  const latestDelta = useMemo(() => {
    const points = rankData?.points ?? [];
    if (points.length < 2) return null;
    const prev = points[points.length - 2].overall_rank;
    const current = points[points.length - 1].overall_rank;
    return prev - current;
  }, [rankData]);

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-3 sm:mb-4">
        <div>
          <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black">Leagues</h1>
        </div>
      </div>

      <section className={`${cardClass} mb-4`}>
        <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 sm:items-center">
          <input
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            placeholder="FPL Team ID"
            inputMode="numeric"
            className="rounded-md h-10 px-3 bg-black/30 border border-white/20 w-full sm:min-w-[240px] sm:w-auto"
          />
          <button
            onClick={() => void run()}
            disabled={loading || !/^\d+$/.test(teamId.trim())}
            className="px-4 h-10 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60 w-full sm:w-auto"
          >
            {loading ? "Loading..." : "Load Leagues"}
          </button>
        </div>
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
        <div className="grid gap-4">
          <section className={cardClass}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
              <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <p className="text-white/65 text-[11px]">Total leagues</p>
                <p className="font-semibold text-base">{formatNum(data.summary.league_count)}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <p className="text-white/65 text-[11px]">Classic</p>
                <p className="font-semibold text-base">{formatNum(data.summary.classic_count)}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                <p className="text-white/65 text-[11px]">H2H</p>
                <p className="font-semibold text-base">{formatNum(data.summary.h2h_count)}</p>
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Insights</h2>
            {data.insights.length === 0 ? (
              <p className="text-white/75 text-sm">No league insights available yet.</p>
            ) : (
              <ul className="grid gap-2 text-sm">
                {data.insights.map((ins, idx) => (
                  <li key={`${ins.type}-${idx}`} className="rounded-md border border-white/10 bg-black/20 p-2.5 leading-relaxed">
                    {formatInsightText(ins.text)}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={cardClass}>
            <div className="flex items-end justify-between gap-3 mb-2">
              <div>
                <h2 className="font-semibold text-[#00ff87]">League Positions</h2>
                <p className="text-xs text-white/65">Classic Pts: {formatNum(classicPts)}</p>
              </div>
              <p className="text-[11px] text-white/60">Showing {formatNum(visibleLeagues.length)}</p>
            </div>

            <div className="sticky top-[56px] z-10 -mx-2 px-2 py-2 mb-3">
              <div className="flex gap-2 overflow-x-auto snap-x snap-mandatory">
                {([
                  ["all", "All"],
                  ["classic", "Classic"],
                  ["h2h", "H2H"],
                ] as const).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setLeagueFilter(value)}
                    className={`px-3.5 py-2 text-xs rounded-full border whitespace-nowrap transition active:scale-[0.98] snap-start ${
                      leagueFilter === value
                        ? "bg-[#00ff87] text-[#37003c] border-[#00ff87] shadow-[0_0_0_1px_rgba(0,255,135,0.4)]"
                        : "border-white/25 text-white/85 hover:border-[#00ff87]/70"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="md:hidden space-y-2">
              {visibleLeagues.map((l) => (
                <div key={`m-${l.type}-${l.league_id}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium leading-tight">{l.name}</p>
                      <p className="text-[11px] text-white/60 uppercase mt-0.5">{l.type}</p>
                    </div>
                    <p className="text-sm font-semibold text-right">
                      #{formatNum(l.your_rank)}
                      <span className="block text-[10px] text-white/60 font-normal">/{formatNum(l.entry_count)} members</span>
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs mt-2">
                    <p className="text-white/75">Δ: <span className={rankDeltaClass(l.rank_delta)}>{rankDeltaLabel(l.rank_delta)}</span></p>
                    <p className="text-white/75">Gap Leader: <span className="text-white">{formatNum(l.gap_to_leader)}</span></p>
                    <p className="text-white/75">Gap ↑: <span className="text-white">{formatNum(l.gap_to_next_above)}</span></p>
                    <p className="text-white/75">Gap ↓: <span className="text-white">{formatNum(l.gap_to_next_below)}</span></p>
                    <p className="text-white/75 col-span-2">{percentileLabelForRow(l)}: <span className="text-white font-medium">{percentileOrH2h(l)}</span></p>
                  </div>
                </div>
              ))}
            </div>

            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/10">
                    <th className="py-2">League</th>
                    <th className="py-2">Rank</th>
                    <th className="py-2">Δ</th>
                    <th className="py-2">Gap Leader</th>
                    <th className="py-2">Gap ↑</th>
                    <th className="py-2">Gap ↓</th>
                    <th className="py-2">{leagueFilter === "classic" ? "Percentile" : leagueFilter === "h2h" ? "H2H Pts" : "Percentile / H2H Pts"}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleLeagues.map((l) => (
                    <tr key={`${l.type}-${l.league_id}`} className="border-b border-white/5 align-top">
                      <td className="py-2">
                        <p className="font-medium">{l.name}</p>
                        <p className="text-[11px] text-white/60 uppercase">{l.type}</p>
                      </td>
                      <td className="py-2">
                        #{formatNum(l.your_rank)}
                        <span className="text-white/60 text-[11px]"> / {formatNum(l.entry_count)} members</span>
                      </td>
                      <td className={`py-2 ${rankDeltaClass(l.rank_delta)}`}>{rankDeltaLabel(l.rank_delta)}</td>
                      <td className="py-2">{formatNum(l.gap_to_leader)}</td>
                      <td className="py-2">{formatNum(l.gap_to_next_above)}</td>
                      <td className="py-2">{formatNum(l.gap_to_next_below)}</td>
                      <td className="py-2">{percentileOrH2h(l)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Overall Rank Trend</h2>
            {rankError ? <p className="text-amber-200 text-sm mb-3">{rankError}</p> : null}
            {rankData ? (
              <>
                <p className="text-sm text-white/75 mb-3">{rankData.summary}</p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4 text-sm">
                  <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
                    Best Rank: <strong>{formatRank(rankData.best_rank)}</strong>
                  </div>
                  <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
                    Worst Rank: <strong>{formatRank(rankData.worst_rank)}</strong>
                  </div>
                  <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2 col-span-2 md:col-span-1">
                    Last GW Delta: <strong>{formatDelta(latestDelta)}</strong>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs md:text-sm">
                    <thead>
                      <tr className="text-left text-white/70 border-b border-white/10">
                        <th className="py-2">GW</th>
                        <th className="py-2">Overall Rank</th>
                        <th className="py-2">Δ vs Prev GW</th>
                        <th className="py-2">GW Points</th>
                        <th className="py-2">Total Points</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rankData.points.map((p, i) => {
                        const prev = i > 0 ? rankData.points[i - 1].overall_rank : null;
                        const delta = prev !== null ? prev - p.overall_rank : null;
                        const deltaClass =
                          delta === null
                            ? "text-white/65"
                            : delta > 0
                            ? "text-[#00ff87]"
                            : delta < 0
                            ? "text-red-300"
                            : "text-white/65";

                        return (
                          <tr key={p.event} className="border-b border-white/5">
                            <td className="py-2">{p.event}</td>
                            <td className="py-2">{formatRank(p.overall_rank)}</td>
                            <td className={`py-2 ${deltaClass}`}>{formatDelta(delta)}</td>
                            <td className="py-2">{formatNum(p.event_points)}</td>
                            <td className="py-2">{formatNum(p.total_points)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="text-white/75 text-sm">Rank trend unavailable.</p>
            )}
          </section>
        </div>
      ) : null}
    </main>
  );
}
