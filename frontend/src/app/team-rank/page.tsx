"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchJson } from "@/lib/api";

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

type AppSettings = {
  fpl_entry_id: number | null;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

function formatRank(n: number | undefined) {
  if (!n) return "-";
  return n.toLocaleString();
}

function formatDelta(delta: number | null): string {
  if (delta === null) return "-";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toLocaleString()}`;
}

export default function TeamRankPage() {
  const [teamId, setTeamId] = useState("");
  const [data, setData] = useState<RankHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const normalizedTeamId = teamId.trim();
  const teamIdValid = /^\d+$/.test(normalizedTeamId);

  useEffect(() => {
    fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings`)
      .then((s) => {
        if (s.fpl_entry_id) {
          setTeamId((prev) => prev || String(s.fpl_entry_id));
        }
      })
      .catch(() => null);
  }, []);

  async function load() {
    if (!normalizedTeamId || !teamIdValid) {
      setError("Team ID must be numeric.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchJson<RankHistoryResponse>(`${API_BASE}/api/fpl/team/${normalizedTeamId}/rank-history`);
      setData(payload);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load rank history");
    } finally {
      setLoading(false);
    }
  }

  const chart = useMemo(() => {
    const points = data?.points ?? [];
    if (points.length < 2) return null;

    const width = 960;
    const height = 300;
    const pad = 36;
    const minRank = Math.min(...points.map((p) => p.overall_rank));
    const maxRank = Math.max(...points.map((p) => p.overall_rank));
    const rankRange = Math.max(1, maxRank - minRank);

    // Invert Y so lower (better) rank goes lower on chart.
    const toX = (index: number) => pad + (index / (points.length - 1)) * (width - pad * 2);
    const toY = (rank: number) => pad + ((maxRank - rank) / rankRange) * (height - pad * 2);

    const path = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(p.overall_rank).toFixed(1)}`)
      .join(" ");

    return { width, height, pad, minRank, maxRank, path, points, toX, toY };
  }, [data]);

  const latestDelta = useMemo(() => {
    const points = data?.points ?? [];
    if (points.length < 2) return null;
    const prev = points[points.length - 2].overall_rank;
    const current = points[points.length - 1].overall_rank;
    return prev - current;
  }, [data]);

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-3xl font-black mb-4">Rank Trend</h1>

      <section className={`${cardClass} mb-6`}>
        <div className="flex gap-3 flex-wrap items-center">
          <input
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            placeholder="FPL Team ID"
            inputMode="numeric"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20 min-w-[220px]"
          />
          <button
            onClick={load}
            disabled={loading || !normalizedTeamId || !teamIdValid}
            className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60"
          >
            {loading ? "Loading..." : "Load Rank History"}
          </button>
        </div>
        {teamId && !teamIdValid ? <p className="text-amber-200 text-sm mt-2">Team ID should contain digits only.</p> : null}
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
        <section className={cardClass}>
          <p className="text-sm text-white/75 mb-3">{data.summary}</p>
          <div className="grid md:grid-cols-3 gap-3 mb-4 text-sm">
            <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
              Best Rank: <strong>{formatRank(data.best_rank)}</strong>
            </div>
            <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
              Worst Rank: <strong>{formatRank(data.worst_rank)}</strong>
            </div>
            <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
              Last GW Delta: <strong>{formatDelta(latestDelta)}</strong>
            </div>
          </div>

          {chart ? (
            <div className="mb-5 overflow-x-auto">
              <svg
                viewBox={`0 0 ${chart.width} ${chart.height}`}
                className="w-full min-w-[760px] h-[300px] rounded-lg bg-black/20 border border-white/10"
              >
                <line
                  x1={chart.pad}
                  y1={chart.pad}
                  x2={chart.pad}
                  y2={chart.height - chart.pad}
                  stroke="rgba(255,255,255,0.25)"
                />
                <line
                  x1={chart.pad}
                  y1={chart.height - chart.pad}
                  x2={chart.width - chart.pad}
                  y2={chart.height - chart.pad}
                  stroke="rgba(255,255,255,0.25)"
                />

                <path d={chart.path} fill="none" stroke="#00ff87" strokeWidth="3" />

                {chart.points.map((p, i) => (
                  <g key={`${p.event}-${i}`}>
                    <circle cx={chart.toX(i)} cy={chart.toY(p.overall_rank)} r="4" fill="#e90052" />
                    <title>{`GW ${p.event}: #${formatRank(p.overall_rank)}`}</title>
                  </g>
                ))}

                <text x={chart.pad + 6} y={chart.pad - 8} fill="rgba(255,255,255,0.8)" fontSize="12">
                  Worst ({formatRank(chart.maxRank)})
                </text>
                <text
                  x={chart.pad + 6}
                  y={chart.height - chart.pad + 18}
                  fill="rgba(255,255,255,0.8)"
                  fontSize="12"
                >
                  Best ({formatRank(chart.minRank)})
                </text>
              </svg>
              <p className="text-xs text-white/60 mt-2">
                Lower rank is better. A downward trend means your overall rank is improving.
              </p>
            </div>
          ) : (
            <p className="text-white/75 mb-4">Need at least 2 gameweeks to draw trend chart.</p>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
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
                {data.points.map((p, i) => {
                  const prev = i > 0 ? data.points[i - 1].overall_rank : null;
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
                      <td className="py-2">{p.event_points}</td>
                      <td className="py-2">{p.total_points}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </main>
  );
}
